#!/usr/bin/env python3
"""
Instagram Scraper - Main entry point.

Usage:
    python -m scraper.main <username> [--max-posts N] [--output FILE]

Examples:
    python -m scraper.main natgeo
    python -m scraper.main natgeo --max-posts 50
    python -m scraper.main natgeo --output natgeo_data.json
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

from .client import InstagramClient
from .config import ScraperConfig
from .models import ScrapeResult


def setup_logging(verbose: bool = False):
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # Reduce noise from httpx
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def serialize_result(result: ScrapeResult) -> dict:
    """Convert ScrapeResult to JSON-serializable dict."""
    return {
        "profile": {
            "user_id": result.profile.user_id,
            "username": result.profile.username,
            "full_name": result.profile.full_name,
            "biography": result.profile.biography,
            "follower_count": result.profile.follower_count,
            "following_count": result.profile.following_count,
            "posts_count": result.profile.posts_count,
            "profile_pic_url": result.profile.profile_pic_url,
            "profile_pic_url_hd": result.profile.profile_pic_url_hd,
            "is_verified": result.profile.is_verified,
            "is_private": result.profile.is_private,
            "is_business_account": result.profile.is_business_account,
            "category_name": result.profile.category_name,
            "external_url": result.profile.external_url,
            "scraped_at": result.profile.scraped_at.isoformat(),
        },
        "posts": [
            {
                "id": post.id,
                "shortcode": post.shortcode,
                "caption": post.caption,
                "like_count": post.like_count,
                "comment_count": post.comment_count,
                "view_count": post.view_count,
                "timestamp": post.timestamp,
                "taken_at_datetime": post.taken_at_datetime.isoformat() if post.taken_at_datetime else None,
                "media_type": post.media_type,
                "is_video": post.is_video,
                "video_duration": post.video_duration,
                "media_urls": post.media_urls,
                "thumbnail_url": post.thumbnail_url,
                "location": {
                    "id": post.location.id,
                    "name": post.location.name,
                    "slug": post.location.slug,
                } if post.location else None,
                "permalink": post.permalink,
                "owner_username": post.owner_username,
                "owner_id": post.owner_id,
                "scraped_at": post.scraped_at.isoformat(),
            }
            for post in result.posts
        ],
        "metadata": {
            "total_posts_scraped": result.total_posts_scraped,
            "has_more_posts": result.has_more_posts,
            "scrape_completed_at": result.scrape_completed_at.isoformat(),
            "errors": result.errors,
        },
    }


async def scrape(
    username: str,
    max_posts: int | None = None,
    output_file: str | None = None,
    proxy: str | None = None,
) -> ScrapeResult:
    """
    Main scraping function.

    Args:
        username: Instagram username to scrape
        max_posts: Maximum number of posts to fetch (None = all)
        output_file: Path to save JSON output
        proxy: Proxy URL (optional)

    Returns:
        ScrapeResult with profile and posts
    """
    logger = logging.getLogger(__name__)

    # Configure scraper
    config = ScraperConfig(
        max_posts=max_posts,
        proxy_url=proxy,
    )

    logger.info(f"Starting scrape for @{username}")
    if max_posts:
        logger.info(f"Max posts: {max_posts}")

    # Run scraper
    async with InstagramClient(config) as client:
        result = await client.scrape_full(username, max_posts=max_posts)

    # Log results
    logger.info(f"Scrape complete!")
    logger.info(f"Profile: @{result.profile.username}")
    logger.info(f"Followers: {result.profile.follower_count:,}")
    logger.info(f"Posts scraped: {result.total_posts_scraped}")

    if result.errors:
        logger.warning(f"Errors encountered: {len(result.errors)}")
        for error in result.errors:
            logger.warning(f"  - {error}")

    # Save output
    if output_file:
        output_path = Path(output_file)
    else:
        # Default output path
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = output_dir / f"{username}_{timestamp}.json"

    output_data = serialize_result(result)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    logger.info(f"Output saved to: {output_path}")

    return result


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Scrape Instagram profile and posts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python -m scraper.main natgeo
    python -m scraper.main natgeo --max-posts 50
    python -m scraper.main natgeo --output natgeo_data.json
    python -m scraper.main natgeo --proxy http://user:pass@proxy:8080
        """,
    )

    parser.add_argument(
        "username",
        help="Instagram username to scrape (without @)",
    )
    parser.add_argument(
        "--max-posts",
        type=int,
        default=None,
        help="Maximum number of posts to scrape (default: all)",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="Output JSON file path (default: output/<username>_<timestamp>.json)",
    )
    parser.add_argument(
        "--proxy",
        type=str,
        default=None,
        help="Proxy URL (e.g., http://user:pass@host:port)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.verbose)

    # Remove @ from username if provided
    username = args.username.lstrip("@")

    # Run scraper
    try:
        result = asyncio.run(
            scrape(
                username=username,
                max_posts=args.max_posts,
                output_file=args.output,
                proxy=args.proxy,
            )
        )

        # Exit with error if no posts were scraped
        if result.total_posts_scraped == 0 and result.profile.posts_count > 0:
            print("Warning: No posts were scraped despite profile having posts.", file=sys.stderr)
            sys.exit(1)

    except KeyboardInterrupt:
        print("\nScraping interrupted by user.", file=sys.stderr)
        sys.exit(130)

    except Exception as e:
        logging.error(f"Scraping failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
