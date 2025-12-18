"""
Instagram HTTP client with automatic token discovery.
No manual cookies or authentication required.
"""

import asyncio
import random
import logging
import json
from typing import Optional

import httpx

from .config import (
    ScraperConfig,
    INSTAGRAM_BASE_URL,
    INSTAGRAM_FEED_URL,
    BLOCK_PATTERNS,
)
from .models import ProfileData, PostData, ScrapeResult, SessionTokens
from .parsers import TokenDiscovery, ProfileParser, PostParser, ParserError
from .utils.headers import HeaderGenerator
from .utils.retry import RetryConfig, with_retry, BlockDetectedError, RetryableError

logger = logging.getLogger(__name__)


class InstagramClient:
    """
    Instagram scraper client with automatic session management.

    This client:
    - Automatically discovers all required tokens (app_id, csrf)
    - Maintains session cookies automatically
    - Requires NO manual cookie copying or OAuth
    - Handles pagination for all posts via feed API
    """

    def __init__(self, config: Optional[ScraperConfig] = None):
        """
        Initialize the Instagram client.

        Args:
            config: Scraper configuration (uses defaults if not provided)
        """
        self.config = config or ScraperConfig()
        self.header_gen = HeaderGenerator(self.config.ua_profile)
        self.tokens: Optional[SessionTokens] = None
        self._client: Optional[httpx.AsyncClient] = None
        self._initialized = False
        self._request_count = 0

    async def __aenter__(self):
        """Async context manager entry."""
        await self._ensure_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def _ensure_client(self):
        """Ensure HTTP client is created."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.config.request_timeout),
                follow_redirects=True,
                http2=False,  # HTTP/2 can cause encoding issues
                proxy=self.config.proxy_url,
            )

    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _delay(self):
        """Add random delay between requests."""
        delay = random.uniform(
            self.config.request_delay_min,
            self.config.request_delay_max
        )
        await asyncio.sleep(delay)

    def _check_for_blocks(self, response: httpx.Response, html: str):
        """
        Check response for block indicators.

        Raises:
            BlockDetectedError: If a block is detected
        """
        # Check URL for redirects to login/challenge
        url_path = str(response.url.path)

        if "/accounts/login" in url_path:
            raise BlockDetectedError("login_required", "Redirected to login page")

        if "/challenge" in url_path:
            raise BlockDetectedError("challenge_required", "Challenge/verification required")

        # If we have og:title meta tag, the page likely has useful data
        # Don't block on content patterns in this case (Dec 2024 update)
        if 'property="og:title"' in html and 'property="og:description"' in html:
            logger.debug("Page has og meta tags - skipping content-based block detection")
            return

        # Check response content for block patterns
        html_lower = html.lower()

        for block_type, patterns in BLOCK_PATTERNS.items():
            for pattern in patterns:
                if pattern.lower() in html_lower:
                    raise BlockDetectedError(block_type, f"Pattern matched: {pattern}")

        # Check for empty/minimal response on profile pages
        if len(html) < 1000 and "username" not in html:
            raise RetryableError("Empty or minimal response received")

    async def initialize(self):
        """
        Initialize the session by discovering all required tokens.
        This visits Instagram's homepage to extract tokens automatically.

        No manual intervention required.
        """
        await self._ensure_client()

        logger.info("Initializing session and discovering tokens...")

        # Visit homepage to get initial cookies and discover tokens
        headers = self.header_gen.get_base_headers()

        response = await self._client.get(
            INSTAGRAM_BASE_URL + "/",
            headers=headers,
        )
        response.raise_for_status()

        # Get CSRF token from cookies
        csrf_token = response.cookies.get("csrftoken", "")
        if not csrf_token:
            # Try to find in response
            for cookie in self._client.cookies.jar:
                if cookie.name == "csrftoken":
                    csrf_token = cookie.value
                    break

        if not csrf_token:
            logger.warning("Could not get CSRF token from cookies")
            csrf_token = ""

        # Discover all tokens from page content
        self.tokens = TokenDiscovery.discover_all(response.text, csrf_token)

        logger.info(f"Session initialized - App ID: {self.tokens.app_id}")
        self._initialized = True

    async def _ensure_initialized(self):
        """Ensure session is initialized before making requests."""
        if not self._initialized:
            await self.initialize()

    @with_retry(RetryConfig(max_attempts=3))
    async def _fetch_profile_page(self, username: str) -> str:
        """
        Fetch a profile page HTML.

        Args:
            username: Instagram username

        Returns:
            Raw HTML content
        """
        await self._ensure_initialized()
        await self._delay()

        url = f"{INSTAGRAM_BASE_URL}/{username}/"
        headers = self.header_gen.get_base_headers()

        logger.debug(f"Fetching profile page: {url}")

        response = await self._client.get(url, headers=headers)
        response.raise_for_status()

        html = response.text
        self._check_for_blocks(response, html)

        # Update CSRF token if changed
        new_csrf = response.cookies.get("csrftoken")
        if new_csrf and self.tokens:
            self.tokens.csrf_token = new_csrf

        self._request_count += 1
        return html

    @with_retry(RetryConfig(max_attempts=3))
    async def _fetch_feed_page(
        self,
        username: str,
        max_id: Optional[str] = None,
        count: int = 12
    ) -> dict:
        """
        Fetch a page of posts using the feed API.
        This is the current working method as of Dec 2024.

        Args:
            username: Instagram username
            max_id: Pagination cursor (next_max_id from previous response)
            count: Number of posts to fetch

        Returns:
            Feed API response data
        """
        await self._ensure_initialized()
        await self._delay()

        # Build URL with params
        url = f"{INSTAGRAM_FEED_URL}/{username}/username/?count={count}"
        if max_id:
            url += f"&max_id={max_id}"

        headers = self.header_gen.get_ajax_headers(
            app_id=self.tokens.app_id if self.tokens else "936619743392459",
            csrf_token=self.tokens.csrf_token if self.tokens else "",
            asbd_id=self.tokens.asbd_id if self.tokens else None,
        )

        logger.debug(f"Fetching feed page for {username}, max_id={max_id[:20] if max_id else 'None'}...")

        response = await self._client.get(url, headers=headers)
        response.raise_for_status()

        # Check for blocks
        text = response.text
        if "login" in text.lower() and "required" in text.lower():
            raise BlockDetectedError("login_required", "Feed API returned login required")

        try:
            data = response.json()
        except json.JSONDecodeError:
            raise RetryableError("Invalid JSON response from feed API")

        # Check for API errors
        if data.get("status") == "fail":
            error_msg = data.get("message", "Unknown error")
            if "rate" in error_msg.lower() or "wait" in error_msg.lower():
                raise RetryableError(f"Rate limited: {error_msg}")
            raise ParserError(f"Feed API error: {error_msg}")

        self._request_count += 1
        return data

    async def scrape_profile(self, username: str) -> ProfileData:
        """
        Scrape profile data for a username.

        Args:
            username: Instagram username

        Returns:
            ProfileData model
        """
        html = await self._fetch_profile_page(username)
        return ProfileParser.parse_from_html(html)

    async def scrape_full(
        self,
        username: str,
        max_posts: Optional[int] = None
    ) -> ScrapeResult:
        """
        Perform a full scrape of profile and all posts.

        Uses the feed API (current working method as of Dec 2024) with
        profile data from HTML meta tags.

        Args:
            username: Instagram username
            max_posts: Maximum posts to fetch (None = all)

        Returns:
            ScrapeResult with profile and posts
        """
        errors = []

        # Scrape profile from HTML meta tags
        try:
            html = await self._fetch_profile_page(username)
            profile = ProfileParser.parse_from_html(html)
        except Exception as e:
            logger.error(f"Failed to scrape profile: {e}")
            raise

        logger.info(f"Profile scraped: {profile.username} ({profile.follower_count} followers)")

        # Get posts via feed API (current working method)
        if max_posts is None:
            max_posts = self.config.max_posts

        all_posts = []
        next_max_id = None
        more_available = True

        while more_available:
            if max_posts and len(all_posts) >= max_posts:
                break

            try:
                data = await self._fetch_feed_page(username, next_max_id)

                # Extract user_id from feed response if we don't have it
                if not profile.user_id and data.get("user"):
                    profile.user_id = str(data["user"].get("pk", ""))

                # Parse posts from feed response
                posts, next_max_id, more_available = PostParser.parse_feed_response(data, username)
                all_posts.extend(posts)

                logger.info(f"Progress: {len(all_posts)} posts fetched")

                if not next_max_id:
                    break

            except BlockDetectedError as e:
                logger.error(f"Block detected during pagination: {e}")
                errors.append(str(e))
                break

            except ParserError as e:
                logger.error(f"Pagination error: {e}")
                errors.append(str(e))
                break

            except Exception as e:
                logger.error(f"Unexpected error during pagination: {e}")
                errors.append(str(e))
                break

        # Trim to max_posts if specified
        if max_posts and len(all_posts) > max_posts:
            all_posts = all_posts[:max_posts]

        return ScrapeResult(
            profile=profile,
            posts=all_posts,
            total_posts_scraped=len(all_posts),
            has_more_posts=more_available and bool(next_max_id),
            errors=errors,
        )
