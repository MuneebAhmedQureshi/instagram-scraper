"""
User-Agent and header generation utilities.
Maintains consistency between UA and related headers.
"""

import random
from typing import Optional


# Realistic browser profiles with consistent header sets
UA_PROFILES = {
    "chrome_windows": {
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "sec_ch_ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        "sec_ch_ua_mobile": "?0",
        "sec_ch_ua_platform": '"Windows"',
        "accept_language": "en-US,en;q=0.9",
    },
    "chrome_mac": {
        "user_agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "sec_ch_ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        "sec_ch_ua_mobile": "?0",
        "sec_ch_ua_platform": '"macOS"',
        "accept_language": "en-US,en;q=0.9",
    },
    "firefox_windows": {
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) "
            "Gecko/20100101 Firefox/121.0"
        ),
        "sec_ch_ua": None,  # Firefox doesn't send these
        "sec_ch_ua_mobile": None,
        "sec_ch_ua_platform": None,
        "accept_language": "en-US,en;q=0.5",
    },
    "safari_mac": {
        "user_agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/17.0 Safari/605.1.15"
        ),
        "sec_ch_ua": None,  # Safari doesn't send these
        "sec_ch_ua_mobile": None,
        "sec_ch_ua_platform": None,
        "accept_language": "en-US,en;q=0.9",
    },
    "edge_windows": {
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
        ),
        "sec_ch_ua": '"Not_A Brand";v="8", "Chromium";v="120", "Microsoft Edge";v="120"',
        "sec_ch_ua_mobile": "?0",
        "sec_ch_ua_platform": '"Windows"',
        "accept_language": "en-US,en;q=0.9",
    },
}


class HeaderGenerator:
    """
    Generates consistent browser headers.
    Once a profile is selected, it remains consistent for the session.
    """

    def __init__(self, profile_name: Optional[str] = None):
        """
        Initialize with a specific profile or random selection.

        Args:
            profile_name: Specific profile to use, or None for random
        """
        if profile_name and profile_name in UA_PROFILES:
            self.profile_name = profile_name
        else:
            self.profile_name = random.choice(list(UA_PROFILES.keys()))

        self.profile = UA_PROFILES[self.profile_name]

    def get_base_headers(self) -> dict[str, str]:
        """Get base headers for all requests."""
        headers = {
            "User-Agent": self.profile["user_agent"],
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": self.profile["accept_language"],
            "Accept-Encoding": "gzip, deflate",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        }

        # Add Chrome-specific headers if applicable
        if self.profile.get("sec_ch_ua"):
            headers["Sec-CH-UA"] = self.profile["sec_ch_ua"]
            headers["Sec-CH-UA-Mobile"] = self.profile["sec_ch_ua_mobile"]
            headers["Sec-CH-UA-Platform"] = self.profile["sec_ch_ua_platform"]

        return headers

    def get_ajax_headers(
        self,
        app_id: str,
        csrf_token: str,
        asbd_id: Optional[str] = None
    ) -> dict[str, str]:
        """
        Get headers for AJAX/GraphQL requests.

        Args:
            app_id: X-IG-App-ID (discovered from page)
            csrf_token: CSRF token (from cookies)
            asbd_id: ASBD ID (optional, discovered from page)
        """
        headers = {
            "User-Agent": self.profile["user_agent"],
            "Accept": "*/*",
            "Accept-Language": self.profile["accept_language"],
            "Accept-Encoding": "gzip, deflate",
            "X-Requested-With": "XMLHttpRequest",
            "X-IG-App-ID": app_id,
            "X-CSRFToken": csrf_token,
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Referer": "https://www.instagram.com/",
        }

        if asbd_id:
            headers["X-ASBD-ID"] = asbd_id

        # Add Chrome-specific headers if applicable
        if self.profile.get("sec_ch_ua"):
            headers["Sec-CH-UA"] = self.profile["sec_ch_ua"]
            headers["Sec-CH-UA-Mobile"] = self.profile["sec_ch_ua_mobile"]
            headers["Sec-CH-UA-Platform"] = self.profile["sec_ch_ua_platform"]

        return headers

    @property
    def user_agent(self) -> str:
        """Get the current user agent string."""
        return self.profile["user_agent"]
