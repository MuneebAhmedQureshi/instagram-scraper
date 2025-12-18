"""
Instagram Scraper - HTTP-based scraper for public Instagram profiles and posts.

This scraper:
- Uses ONLY HTTP requests (no browser automation)
- Automatically discovers all required tokens (no manual cookies)
- Supports full pagination for all posts
- Extracts all required profile and post data
"""

from .client import InstagramClient
from .models import ProfileData, PostData, ScrapeResult
from .config import ScraperConfig

__version__ = "1.0.0"
__all__ = [
    "InstagramClient",
    "ProfileData",
    "PostData",
    "ScrapeResult",
    "ScraperConfig",
]
