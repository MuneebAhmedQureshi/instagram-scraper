"""
Configuration settings for Instagram scraper.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ScraperConfig:
    """Main configuration for the scraper."""

    # Request settings
    request_timeout: float = 30.0
    request_delay_min: float = 2.0  # Minimum seconds between requests
    request_delay_max: float = 5.0  # Maximum seconds between requests

    # Pagination settings
    posts_per_page: int = 12  # Instagram returns 12 posts per page
    max_posts: Optional[int] = None  # None = fetch all posts

    # Retry settings
    max_retries: int = 5
    retry_base_delay: float = 2.0
    retry_max_delay: float = 300.0

    # Proxy settings
    proxy_url: Optional[str] = None
    rotate_proxy_after: int = 15  # Rotate after N requests

    # Output settings
    output_dir: str = "output"
    save_raw_html: bool = False

    # User agent profile (None = random)
    ua_profile: Optional[str] = None


# Default Instagram endpoints
INSTAGRAM_BASE_URL = "https://www.instagram.com"
INSTAGRAM_API_URL = f"{INSTAGRAM_BASE_URL}/api/v1"
INSTAGRAM_FEED_URL = f"{INSTAGRAM_API_URL}/feed/user"

# Regex patterns for auto-discovery
PATTERNS = {
    # App ID patterns - found in page source
    "app_id": r'"X-IG-App-ID":"(\d+)"',
    "app_id_alt": r'{"APP_ID":"(\d+)"',

    # ASBD ID pattern
    "asbd_id": r'"X-ASBD-ID":"(\d+)"',
}

# Known fallback values (use only if discovery fails)
# These WILL break eventually - discovery is preferred
FALLBACK_VALUES = {
    "app_id": "936619743392459",
    "asbd_id": "129477",
}

# Block detection patterns (checked only when og meta tags not present)
BLOCK_PATTERNS = {
    "login_required": [
        "Login required",
        "Please wait a few minutes before you try again",
    ],
    "challenge_required": [
        "checkpoint_required",
    ],
    "not_found": [
        "Page not found",
        "Sorry, this page isn",
    ],
    "rate_limited": [
        "Please wait a few minutes",
        "rate limit",
    ],
}
