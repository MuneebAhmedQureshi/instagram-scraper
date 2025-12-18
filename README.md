# Instagram Scraper

Scrapes public Instagram profiles and posts using HTTP requests. No browser automation, no manual cookies, no OAuth - just run it.

## Architecture

See [architecture/DESIGN.md](architecture/DESIGN.md) for detailed system design documentation.

## Requirements

- Python 3.10+

## Installation

```bash
# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate  # Linux/Mac
# OR: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

## Usage

```bash
# Make sure venv is activated first
source venv/bin/activate

# Scrape a profile (gets profile info + all posts)
python -m scraper.main natgeo

# Limit number of posts
python -m scraper.main natgeo --max-posts 50

# Save to specific file
python -m scraper.main natgeo --output myfile.json

# Verbose logging
python -m scraper.main natgeo -v

# With proxy
python -m scraper.main natgeo --proxy http://user:pass@proxy:8080
```

## Output

Results are saved as JSON in the `output/` folder with profile data and posts:

```json
{
  "profile": {
    "username": "natgeo",
    "full_name": "National Geographic",
    "follower_count": 283000000,
    "following_count": 134,
    "posts_count": 29847
  },
  "posts": [
    {
      "shortcode": "C2abc123",
      "caption": "Photo by @photographer...",
      "like_count": 450000,
      "comment_count": 1234,
      "media_type": "image",
      "permalink": "https://www.instagram.com/p/C2abc123/"
    }
  ]
}
```

## Troubleshooting

**"Block detected: login_required"**
- Instagram is blocking this IP. Use a proxy or wait 15-30 minutes.

**"Rate limited"**
- Too many requests. The scraper will auto-retry with delays.

## Limitations

- Only works with **public** accounts
- Instagram may change their API without notice
- No comment scraping (profile + posts only)

### Profile Fields Requiring Authentication

The following profile fields cannot be retrieved without Instagram authentication:

| Field | Status | Reason |
|-------|--------|--------|
| `is_verified` | Always `false` | Requires authenticated API |
| `category_name` | Always `null` | Requires authenticated API |
| `external_url` | Always `null` | Requires authenticated API |

These fields are included in the output schema but will have default/null values when scraping without authentication. All other profile fields (username, full_name, biography, follower_count, following_count, posts_count, profile_pic_url) are fully available from public HTML meta tags.
