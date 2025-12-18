"""
Data models for Instagram scraper using Pydantic for validation.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class Location(BaseModel):
    """Location data attached to a post."""
    id: str
    name: str
    slug: Optional[str] = None


class ProfileData(BaseModel):
    """Instagram profile/user data."""
    user_id: str = Field(default="", description="Instagram user ID (may be empty if scraped from meta tags)")
    username: str
    full_name: str = ""
    biography: str = ""
    follower_count: int = 0
    following_count: int = 0
    posts_count: int = 0
    profile_pic_url: str = ""
    profile_pic_url_hd: Optional[str] = None
    is_verified: bool = False
    is_private: bool = False
    is_business_account: bool = False
    category_name: Optional[str] = None
    external_url: Optional[str] = None
    fbid: Optional[str] = None
    scraped_at: datetime = Field(default_factory=datetime.utcnow)


class PostData(BaseModel):
    """Instagram post data."""
    id: str = Field(..., description="Post ID (numeric)")
    shortcode: str = Field(..., description="Post shortcode for URL")
    caption: Optional[str] = None
    like_count: int = 0
    comment_count: int = 0
    view_count: Optional[int] = None
    timestamp: int = Field(..., description="Unix timestamp")
    taken_at_datetime: Optional[datetime] = None
    media_type: str = Field(..., description="image, video, carousel, or reel")
    is_video: bool = False
    video_duration: Optional[float] = None
    media_urls: list[str] = Field(default_factory=list)
    thumbnail_url: Optional[str] = None
    location: Optional[Location] = None
    permalink: str = ""
    owner_username: str = ""
    owner_id: str = ""
    scraped_at: datetime = Field(default_factory=datetime.utcnow)

    def __init__(self, **data):
        super().__init__(**data)
        # Auto-generate permalink if not provided
        if not self.permalink and self.shortcode:
            self.permalink = f"https://www.instagram.com/p/{self.shortcode}/"
        # Convert timestamp to datetime
        if self.timestamp and not self.taken_at_datetime:
            self.taken_at_datetime = datetime.utcfromtimestamp(self.timestamp)


class ScrapeResult(BaseModel):
    """Complete scrape result for an account."""
    profile: ProfileData
    posts: list[PostData] = Field(default_factory=list)
    total_posts_scraped: int = 0
    has_more_posts: bool = False
    scrape_completed_at: datetime = Field(default_factory=datetime.utcnow)
    errors: list[str] = Field(default_factory=list)


class SessionTokens(BaseModel):
    """Auto-discovered session tokens."""
    app_id: str
    csrf_token: str
    asbd_id: Optional[str] = None
