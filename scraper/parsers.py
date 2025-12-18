"""
Parsers for extracting data from Instagram HTML and JSON responses.
"""

import html as html_lib
import re
import logging
from typing import Optional

from .models import ProfileData, PostData, Location, SessionTokens
from .config import PATTERNS, FALLBACK_VALUES

logger = logging.getLogger(__name__)


class ParserError(Exception):
    """Raised when parsing fails."""
    pass


class TokenDiscovery:
    """Discovers required tokens from Instagram pages automatically."""

    @staticmethod
    def extract_app_id(html: str) -> str:
        """Extract X-IG-App-ID from page source."""
        match = re.search(PATTERNS["app_id"], html)
        if match:
            return match.group(1)

        match = re.search(PATTERNS["app_id_alt"], html)
        if match:
            return match.group(1)

        return FALLBACK_VALUES["app_id"]

    @staticmethod
    def extract_asbd_id(html: str) -> Optional[str]:
        """Extract X-ASBD-ID from page source."""
        match = re.search(PATTERNS["asbd_id"], html)
        if match:
            return match.group(1)
        return FALLBACK_VALUES.get("asbd_id")

    @classmethod
    def discover_all(cls, html: str, csrf_token: str) -> SessionTokens:
        """Discover all required tokens from page HTML."""
        return SessionTokens(
            app_id=cls.extract_app_id(html),
            csrf_token=csrf_token,
            asbd_id=cls.extract_asbd_id(html),
        )


class ProfileParser:
    """Parses profile data from Instagram HTML meta tags."""

    @staticmethod
    def parse_count_string(count_str: str) -> int:
        """Parse count strings like '276M', '31K', '1.5B' to integers."""
        if not count_str:
            return 0

        count_str = count_str.strip().replace(',', '')
        multipliers = {'K': 1000, 'M': 1000000, 'B': 1000000000}

        for suffix, mult in multipliers.items():
            if count_str.endswith(suffix):
                try:
                    return int(float(count_str[:-1]) * mult)
                except ValueError:
                    return 0

        try:
            return int(count_str)
        except ValueError:
            return 0

    @staticmethod
    def extract_from_meta_tags(html: str) -> Optional[dict]:
        """
        Extract profile data from HTML meta tags.

        Returns dict with: username, full_name, follower_count, following_count,
                          posts_count, profile_pic_url, biography
        """
        data = {}

        # Extract og:title - contains "Full Name (@username)"
        title_match = re.search(r'<meta property="og:title" content="([^"]+)"', html)
        if title_match:
            title = html_lib.unescape(title_match.group(1))
            name_match = re.search(r'^(.+?)\s*\(@(\w+)\)', title)
            if name_match:
                data['full_name'] = name_match.group(1).strip()
                data['username'] = name_match.group(2)

        # Extract og:description - contains follower/following/posts counts
        desc_match = re.search(r'<meta property="og:description" content="([^"]+)"', html)
        if desc_match:
            desc = html_lib.unescape(desc_match.group(1))

            follower_match = re.search(r'([\d.,]+[KMB]?)\s*Followers', desc, re.IGNORECASE)
            if follower_match:
                data['follower_count'] = ProfileParser.parse_count_string(follower_match.group(1))

            following_match = re.search(r'([\d.,]+[KMB]?)\s*Following', desc, re.IGNORECASE)
            if following_match:
                data['following_count'] = ProfileParser.parse_count_string(following_match.group(1))

            posts_match = re.search(r'([\d.,]+[KMB]?)\s*Posts', desc, re.IGNORECASE)
            if posts_match:
                data['posts_count'] = ProfileParser.parse_count_string(posts_match.group(1))

            # Extract bio snippet
            bio_match = re.search(r'Posts\s*[-–]\s*(.+?)(?:$|\s*See Instagram)', desc)
            if bio_match:
                data['biography'] = bio_match.group(1).strip()

        # Extract og:image - profile picture
        img_match = re.search(r'<meta property="og:image" content="([^"]+)"', html)
        if img_match:
            data['profile_pic_url'] = html_lib.unescape(img_match.group(1))

        return data if data else None

    @classmethod
    def parse_from_html(cls, html: str) -> ProfileData:
        """Parse profile data from raw HTML."""
        meta_data = cls.extract_from_meta_tags(html)
        if meta_data:
            return ProfileData(
                user_id="",
                username=meta_data.get('username', ''),
                full_name=meta_data.get('full_name', ''),
                biography=meta_data.get('biography', ''),
                follower_count=meta_data.get('follower_count', 0),
                following_count=meta_data.get('following_count', 0),
                posts_count=meta_data.get('posts_count', 0),
                profile_pic_url=meta_data.get('profile_pic_url', ''),
            )

        raise ParserError("Could not extract profile data from HTML")


class PostParser:
    """Parses post data from Instagram Feed API responses."""

    @staticmethod
    def parse_feed_item(item: dict, owner_username: str = "") -> PostData:
        """Parse a post item from the feed API response."""
        post_id = str(item.get("pk", item.get("id", "")))
        shortcode = item.get("code", "")

        # Caption
        caption = None
        caption_obj = item.get("caption")
        if caption_obj and isinstance(caption_obj, dict):
            caption = caption_obj.get("text")

        # Engagement metrics
        like_count = item.get("like_count", 0)
        comment_count = item.get("comment_count", 0)
        view_count = item.get("play_count") or item.get("view_count")

        # Timestamp
        timestamp = item.get("taken_at", 0)

        # Media type
        media_type_code = item.get("media_type", 1)
        product_type = item.get("product_type", "")

        if media_type_code == 8:
            media_type = "carousel"
        elif media_type_code == 2:
            media_type = "reel" if product_type == "clips" else "video"
        else:
            media_type = "image"

        is_video = media_type_code == 2

        # Media URLs
        media_urls = PostParser._extract_media_urls(item)

        # Thumbnail
        thumbnail_url = ""
        if "image_versions2" in item:
            candidates = item["image_versions2"].get("candidates", [])
            if candidates:
                thumbnail_url = candidates[0].get("url", "")

        # Location
        location = None
        loc_data = item.get("location")
        if loc_data and isinstance(loc_data, dict):
            location = Location(
                id=str(loc_data.get("pk", loc_data.get("id", ""))),
                name=loc_data.get("name", ""),
                slug=loc_data.get("slug"),
            )

        # Owner info
        owner = item.get("user", {})
        owner_id = str(owner.get("pk", ""))
        if not owner_username:
            owner_username = owner.get("username", "")

        return PostData(
            id=post_id,
            shortcode=shortcode,
            caption=caption,
            like_count=like_count,
            comment_count=comment_count,
            view_count=view_count,
            timestamp=timestamp,
            media_type=media_type,
            is_video=is_video,
            video_duration=item.get("video_duration"),
            media_urls=media_urls,
            thumbnail_url=thumbnail_url,
            location=location,
            owner_username=owner_username,
            owner_id=owner_id,
        )

    @staticmethod
    def _extract_media_urls(item: dict) -> list[str]:
        """Extract all media URLs from a feed API post item."""
        urls = []

        # Single image
        if "image_versions2" in item:
            candidates = item["image_versions2"].get("candidates", [])
            if candidates:
                urls.append(candidates[0].get("url", ""))

        # Video
        if "video_versions" in item:
            video_versions = item.get("video_versions", [])
            if video_versions:
                urls.append(video_versions[0].get("url", ""))

        # Carousel items
        for child in item.get("carousel_media", []):
            if "image_versions2" in child:
                candidates = child["image_versions2"].get("candidates", [])
                if candidates:
                    urls.append(candidates[0].get("url", ""))
            if "video_versions" in child:
                video_versions = child.get("video_versions", [])
                if video_versions:
                    urls.append(video_versions[0].get("url", ""))

        return urls

    @staticmethod
    def parse_feed_response(data: dict, owner_username: str = "") -> tuple[list[PostData], Optional[str], bool]:
        """
        Parse feed API response.

        Returns:
            Tuple of (posts list, next_max_id for pagination, more_available)
        """
        items = data.get("items", [])
        next_max_id = data.get("next_max_id")
        more_available = data.get("more_available", False)

        posts = []
        for item in items:
            try:
                post = PostParser.parse_feed_item(item, owner_username)
                posts.append(post)
            except Exception as e:
                logger.warning(f"Failed to parse feed item: {e}")

        return posts, next_max_id, more_available
