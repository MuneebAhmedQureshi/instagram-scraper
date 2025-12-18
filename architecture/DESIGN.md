# Instagram Scraper - Architecture Design

## A. How We Access Data

### Data Sources (No Authentication Required)

The scraper uses **public Instagram endpoints only** - no paid APIs, no browser automation.

| Source | Endpoint | Data Retrieved |
|--------|----------|----------------|
| Profile Page | `instagram.com/{username}/` | Profile metadata from HTML meta tags (og:title, og:description, og:image) |
| Feed API | `instagram.com/api/v1/feed/user/{username}/username/` | Posts with full details, supports pagination via `max_id` |

### Token Discovery (Fully Automatic)

All required tokens are discovered automatically at runtime:

```
1. GET instagram.com/ (homepage)
   └─> Extract: csrftoken (from cookies), X-IG-App-ID (from HTML)

2. GET instagram.com/{username}/ (profile page)
   └─> Extract: Profile data from meta tags

3. GET /api/v1/feed/user/{username}/username/
   └─> Returns: Posts + next_max_id for pagination
```

**No manual cookie copying, no OAuth, no GraphQL doc_id discovery required.**

---

## B. Scraper Structure

### Worker Flow

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Initialize     │────>│  Scrape Profile │────>│  Scrape Posts   │
│  Session        │     │  (HTML meta)    │     │  (Feed API)     │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
                                                         ▼
                                               ┌─────────────────┐
                                               │  Paginate with  │
                                               │  max_id cursor  │◄──┐
                                               └────────┬────────┘   │
                                                        │            │
                                                        ▼            │
                                               ┌─────────────────┐   │
                                               │ more_available? │───┘
                                               └────────┬────────┘
                                                        │ No
                                                        ▼
                                               ┌─────────────────┐
                                               │  Output JSON    │
                                               └─────────────────┘
```

### Retry / Backoff Strategy

| Condition | Action |
|-----------|--------|
| HTTP 429 (Rate Limited) | Exponential backoff: 10s, 20s, 40s, 80s (5x base delay) |
| HTTP 500/502/503/504 | Exponential backoff: 2s, 4s, 8s, 16s |
| Connection Error | Retry 3x with exponential backoff |
| Login Wall Detected | Stop scraping, report block |

```python
RETRY_CONFIG = {
    "max_attempts": 5,
    "base_delay": 2.0,
    "max_delay": 300.0,
    "exponential_base": 2,
    "jitter": True  # Randomize delays ±25%
}
```

### Block Detection

The scraper detects blocks through multiple signals:

1. **URL Redirect** - Redirected to `/accounts/login` or `/challenge`
2. **Response Content** - "Login required", "Please wait", "rate limit"
3. **Empty Response** - Page < 1000 chars without expected data
4. **API Error** - Feed API returns `status: fail`

When meta tags (og:title, og:description) are present, content-based detection is skipped to avoid false positives.

### Proxy Strategy

```bash
# Optional proxy support via CLI
python -m scraper.main username --proxy http://user:pass@proxy:8080
```

- Single proxy per session (sticky for pagination consistency)
- Proxy rotation on block detection (manual)
- Recommended: Residential proxies for best success rate

### User-Agent Strategy

Consistent browser fingerprinting per session:

| Profile | Platform | Headers |
|---------|----------|---------|
| Chrome Windows | Win10 | Full Sec-CH-UA headers |
| Chrome Mac | macOS | Full Sec-CH-UA headers |
| Firefox Windows | Win10 | No Sec-CH-UA (Firefox doesn't send) |
| Safari Mac | macOS | No Sec-CH-UA (Safari doesn't send) |
| Edge Windows | Win10 | Full Sec-CH-UA headers |

One profile is randomly selected per session and used consistently for all requests.

---

## C. Raw Data Collected

### Profile Fields

| Field | Source | Notes |
|-------|--------|-------|
| username | og:title | Always available |
| full_name | og:title | Always available |
| biography | og:description | Truncated snippet |
| follower_count | og:description | Parsed from "276M Followers" |
| following_count | og:description | Parsed from "173 Following" |
| posts_count | og:description | Parsed from "31K Posts" |
| profile_pic_url | og:image | Always available |
| is_verified | - | Requires authentication |
| category_name | - | Requires authentication |
| external_url | - | Requires authentication |

### Post Fields

| Field | Source | Notes |
|-------|--------|-------|
| id | Feed API `pk` | Always available |
| shortcode | Feed API `code` | Always available |
| caption | Feed API `caption.text` | May be null |
| like_count | Feed API `like_count` | Always available |
| comment_count | Feed API `comment_count` | Always available |
| view_count | Feed API `play_count` | Videos/Reels only |
| timestamp | Feed API `taken_at` | Unix timestamp |
| media_type | Feed API `media_type` | image/video/carousel/reel |
| media_urls | Feed API `image_versions2`, `video_versions` | All media |
| location | Feed API `location` | If tagged |
| permalink | Generated | `instagram.com/p/{shortcode}/` |

---

## D. Frequency / Scheduling

### Single Scrape (Current Implementation)

```bash
python -m scraper.main {username} --max-posts N
```

### Production Scheduling (Extension)

For continuous scraping at scale:

| Account Tier | Profile Refresh | Posts Check |
|--------------|-----------------|-------------|
| High Priority (>1M followers) | Every 6 hours | Every 2 hours |
| Medium (100K-1M) | Every 24 hours | Every 12 hours |
| Standard (<100K) | Every 48 hours | Every 24 hours |

### Incremental Scraping (Extension)

```python
# Only fetch posts newer than last scrape
async def incremental_scrape(username, last_timestamp):
    for post in paginate_posts(username):
        if post.timestamp <= last_timestamp:
            break  # Stop at known posts
        yield post
```

---

## E. Account Discovery (Extension)

For scaling to discover new accounts:

1. **Seed List** - Manual list of initial accounts
2. **Related Accounts** - Instagram suggests similar profiles
3. **Mentions** - Extract @mentions from captions
4. **Hashtags** - Scrape posts from relevant hashtags

---

## Technical Stack

- **Language**: Python 3.10+
- **HTTP Client**: httpx (async, HTTP/1.1)
- **Data Validation**: Pydantic
- **No Browser Automation**: Pure HTTP requests
- **No External APIs**: Direct Instagram endpoints only
