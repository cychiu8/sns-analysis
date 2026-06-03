# Japan TEDx Instagram Analysis

Interactive dashboard for analyzing Instagram posts from Japan TEDx accounts, with a companion scraping script to collect the data.

## Overview

| File | Role |
|---|---|
| `ig_scraper.py` | Fetches public Instagram posts via Instaloader and exports CSVs |
| `app.py` | Streamlit dashboard that visualizes the exported data |
| `data/` | Pre-scraped CSVs for 7 Japan TEDx accounts |

**Target accounts:** tedxutokyo, tedxkyoto, tedxkeiou, tedxwasedau, tedxawaji, tedxkobe, tedxhamamatsu

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Running the Dashboard

```bash
streamlit run app.py
```

The app reads `data/tedx_account_all_v2.csv` and `data/tedx_posts_all_v2.csv`. Pre-scraped data is already included in the `data/` directory.

## Changelog

### Latest update
- **Data scope:** All analysis now limited to posts from 2023 onwards (`START_YEAR` in scraper, `load_data()` in dashboard)
- **New scraped fields:** `is_pinned`, `mediacount`, `video_view_count`, `video_play_count`, `video_duration`
- **New dashboard analyses (Tab 2 — Post Type):**
  - View-to-engagement conversion rate by account (likes+comments ÷ video views × 100)
  - View-to-engagement conversion rate by theme (Reels only)
  - Reel duration bucket analysis (short ≤15s / mid 15–30s / long 30s+): avg engagement rate and conversion rate per bucket
  - Theme × Reel duration conversion rate chart (hidden until sample size grows)
- **KPI fix:** "Best engagement rate account" card now computed from filtered post data instead of pre-aggregated CSV
- **CSV output:** All files now saved under `data/` directory

## Dashboard Features

| Tab | Contents |
|---|---|
| Account Overview | Follower counts, engagement rates, per-account comparison table |
| Post Type | Reel vs. Carousel vs. Photo breakdown; theme × type ER; video metrics (conversion rate, duration analysis) |
| Posting Timing | Day-of-week trends, time-band bars, weekday × time heatmap |
| Content Themes | Rule-based theme classification across 6 categories |
| Hashtags | Top-N tag frequency, tag count vs. engagement correlation |
| Top Posts | Top 20 by engagement, full filtered data export (CSV) |

### Content Theme Categories

Themes are assigned by keyword scoring. A single post can carry multiple themes:

- **応募・募集** — Recruitment and applications
- **スピーカー紹介** — Speaker introductions
- **理念・メッセージ** — Mission and values
- **舞台裏・チーム** — Behind-the-scenes / team
- **イベント回顧** — Event recaps
- **その他** — Uncategorized

## Re-scraping Data

1. Save your Instagram session with Instaloader:
   ```bash
   instaloader --login YOUR_USERNAME
   ```

2. Edit the config block at the top of `ig_scraper.py`:
   ```python
   TARGETS    = ["tedxhamamatsu", ...]  # accounts to scrape
   MAX_POSTS  = 200                     # posts per account
   LOGIN_USER = "your_ig_username"
   ```

3. Run the scraper:
   ```bash
   python ig_scraper.py
   ```

   Per-account output: `{account}_posts.csv`, `{account}_summary.csv`  
   Combined output: `tedx_posts_all.csv`, `tedx_account_all.csv`

> **Note:** Instagram rate-limits anonymous requests aggressively. A logged-in session and the built-in sleep delays (`SLEEP_SEC`, `SLEEP_BETWEEN_ACCOUNTS`) are required for reliable scraping. Follow Instagram's Terms of Service.

## Data Schema

### Posts CSV (`tedx_posts_all_v2.csv`)

| Column | Description |
|---|---|
| `account` | TEDx account handle |
| `shortcode` | Instagram post ID |
| `datetime` | Post timestamp (local) |
| `weekday` | Day of week (Mon–Sun) |
| `hour` | Hour of posting (0–23) |
| `type` | `Reel`, `GraphSidecar`, or `photo` |
| `is_pinned` | Whether the post is pinned on the profile |
| `mediacount` | Number of media items (carousel slide count) |
| `likes` / `comments` | Raw counts |
| `engagement` | likes + comments |
| `video_view_count` | View count (video posts only) |
| `video_play_count` | Play count including replays (video posts only) |
| `video_duration` | Duration in seconds (video posts only) |
| `engagement_rate` | engagement / followers × 100 |
| `words` | Caption character count |
| `hashtag_count` | Number of hashtags |
| `primary_hashtags` | First 10 hashtags |
| `caption` | Full caption text |
| `followers` | Follower count at scrape time |

### Account Summary CSV (`tedx_account_all_v2.csv`)

Long-format table with columns `account`, `block`, `metric`, `dimension`, `value`.  
Filter by the `block` column to feed specific charts (`overview`, `post_type`, `weekday`, `time_band`, `posting_frequency`).
