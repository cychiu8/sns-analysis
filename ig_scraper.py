#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TEDx Instagram post analysis | data scraping script
Flow: Instaloader fetches public posts → aggregate metrics → export CSV (for Google Sheets / Looker Studio)

[Install] pip install instaloader
[Run]     python ig_scraper.py
[Note]    Anonymous scraping is often blocked; set LOGIN_USER to your own IG account.
          Follow Instagram's Terms of Service and slow down the fetch rate to avoid rate-limiting.
"""

import csv
import time
import statistics
from collections import defaultdict
import instaloader

# ---------------- Config (adjust as needed) ----------------
TARGETS = ["tedxutokyo", "tedxkyoto", "tedxkeiou", "tedxwasedau", "tedxawaji", "tedxkobe", "tedxhamamatsu"] # list of accounts to analyze
MAX_POSTS  = 200                     # max posts to fetch (None = all); 100–200 recommended
LOGIN_USER  = "cy_.321"              # your IG username
SLEEP_SEC  = 2                       # seconds between posts to reduce rate-limiting risk
SLEEP_BETWEEN_ACCOUNTS = 30 
POSTS_CSV      = "tedx_posts_all.csv"     # All-account per-post detail
ACCOUNT_CSV    = "tedx_account_all.csv"   # Per-account summary
COMPARE_CSV    = "tedx_compare.csv"       # Account comparison
# -----------------------------------------------------------

WEEK = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def classify_type(post):
    """Classify post type."""
    t = post.typename
    if t == "GraphSidecar":
        return "GraphSidecar"
    if t == "GraphVideo":
        return "Reel"
    return "photo"

def time_band(hour):
    """Map posting hour to a named time band."""
    if 5 <= hour < 11:
        return "morning(05-10)"
    if 11 <= hour < 14:
        return "midday(11-13)"
    if 14 <= hour < 18:
        return "afternoon(14-17)"
    if 18 <= hour < 22:
        return "evening(18-21)"
    return "night(22-04)"

def _avg(nums):
    return round(statistics.mean(nums), 2) if nums else 0

def scrape_posts(account, profile, followers):
    rows = []
    for i, post in enumerate(profile.get_posts()):
        if MAX_POSTS and i >= MAX_POSTS:
            break

        dt = post.date_local
        likes = post.likes or 0
        comments = post.comments or 0
        engagement = likes + comments
        caption = (post.caption or "").replace("\n", " ").strip()
        hashtags = post.caption_hashtags
        ptype = classify_type(post)

        rows.append({
            "account": account,
            "shortcode": post.shortcode,
            "url": f"https://www.instagram.com/p/{post.shortcode}/",
            "datetime": dt.strftime("%Y-%m-%d %H:%M"),
            "year-month": dt.strftime("%Y-%m"),
            "weekday": WEEK[dt.weekday()],
            "hour": dt.hour,
            "type": ptype,
            "likes": likes,
            "comments": comments,
            "engagement": engagement,
            "video_view_count": post.video_view_count if post.is_video else "",
            "engagement_rate": round(engagement / followers * 100, 3) if followers else "",
            "words": len(caption),
            "hashtag_count": len(hashtags),
            "primary_hashtags": " ".join(hashtags[:10]),
            "caption": caption,
            "followers": followers,
        })
        print(f"  [{i+1}] {dt:%Y-%m-%d} {ptype} likes:{likes} comments:{comments}")
        time.sleep(SLEEP_SEC)
    return rows


def build_account_summary(account, profile, followers, rows):
    """
    Build account-level summary in a long-table format:
    block + metric + dimension + value.
    Use 'block' as a filter in Looker Studio to feed multiple charts from one table.
    """
    out = []

    def add(block, metric, dim, value):
        out.append({"account": account, "block": block, "metric": metric, "dimension": dim, "value": value})

    eng_rates = [r["engagement_rate"] for r in rows if r["engagement_rate"] != ""]
    likes     = [r["likes"] for r in rows]
    comments  = [r["comments"] for r in rows]
    engs      = [r["engagement"] for r in rows]

    # ---- Block 1: overview (scorecard) ----
    add("overview", "followers", "—", followers)
    add("overview", "total_posts", "—", profile.mediacount)
    add("overview", "analyzed_posts", "—", len(rows))
    add("overview", "avg_engagement_rate", "—", _avg(eng_rates))
    add("overview", "avg_likes", "—", _avg(likes))
    add("overview", "avg_comments", "—", _avg(comments))
    add("overview", "avg_engagement", "—", _avg(engs))
    add("overview", "max_single_post_engagement", "—", max(engs) if engs else 0)
    add("overview", "comment_like_ratio", "—",
        round(sum(comments) / sum(likes) * 100, 2) if sum(likes) else 0)

    # ---- Block 2: by post type ----
    by_type = defaultdict(list)
    for r in rows:
        by_type[r["type"]].append(r)
    for form, items in by_type.items():
        rates = [x["engagement_rate"] for x in items if x["engagement_rate"] != ""]
        add("post_type", "post_count", form, len(items))
        add("post_type", "share(%)", form, round(len(items) / len(rows) * 100, 1))
        add("post_type", "avg_engagement_rate(%)", form, _avg(rates))
        add("post_type", "avg_engagement", form, _avg([x["engagement"] for x in items]))

    # ---- Block 3: by weekday ----
    by_week = defaultdict(list)
    for r in rows:
        by_week[r["weekday"]].append(r)
    for wd in WEEK:
        items = by_week.get(wd, [])
        rates = [x["engagement_rate"] for x in items if x["engagement_rate"] != ""]
        add("weekday", "post_count", wd, len(items))
        add("weekday", "avg_engagement_rate(%)", wd, _avg(rates))

    # ---- Block 4: by time band ----
    by_band = defaultdict(list)
    for r in rows:
        by_band[r["hour"]].append(r)
    for band in ["morning(05-10)", "midday(11-13)", "afternoon(14-17)", "evening(18-21)", "night(22-04)"]:
        items = by_band.get(band, [])
        rates = [x["engagement_rate"] for x in items if x["engagement_rate"] != ""]
        add("time_band", "post_count", band, len(items))
        add("time_band", "avg_engagement_rate(%)", band, _avg(rates))

    # ---- Block 5: posting frequency ----
    by_month = defaultdict(int)
    for r in rows:
        by_month[r["year-month"]] += 1
    if by_month:
        add("posting_frequency", "active_months", "—", len(by_month))
        add("posting_frequency", "avg_posts_per_month", "—", _avg(list(by_month.values())))
        for ym in sorted(by_month):
            add("posting_frequency", "monthly_posts", ym, by_month[ym])

    return out


def write_csv(path, rows):
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main():

    if not LOGIN_USER:
        raise ValueError("Please set LOGIN_USER to your Instagram username")
    L = instaloader.Instaloader(
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False,
    )
    L.load_session_from_file(LOGIN_USER)

    all_posts, all_summary = [], []

    for n, account in enumerate(TARGETS):
        print(f"\n=== Scraping @{account} ===")
        try:
            profile = instaloader.Profile.from_username(L.context, account)
        except Exception as e:
            print(f"Error fetching profile for @{account}: {e}")
            continue

        followers = profile.followers
        print(f"account: {account}  followers: {followers}  total posts: {profile.mediacount}")

        rows = scrape_posts(account, profile, followers)
        if not rows:
            print("No posts fetched (possibly rate-limited or login required). Please check LOGIN_USER and try again.")
            continue

        # Save post-level data
        output_csv = f"{account}_posts.csv"
        write_csv(output_csv, rows)
        print(f"Saved {len(rows)} posts to {output_csv}")

        # Save account summary
        summary_rows = build_account_summary(account, profile, followers, rows)
        summary_csv = f"{account}_summary.csv"
        write_csv(summary_csv, summary_rows)
        print(f"Saved account summary to {summary_csv}")

        all_posts.extend(rows)
        all_summary.extend(summary_rows)

        time.sleep(SLEEP_BETWEEN_ACCOUNTS)
    
    if not all_posts:
        print("\nNo data scraped for any account. Make sure you're logged in and not rate-limited.")
        return
    
    write_csv(POSTS_CSV, all_posts)
    write_csv(ACCOUNT_CSV, all_summary)
    print(f"\n[1/2] All-account detail -> {POSTS_CSV} ({len(all_posts)} rows)")
    print(f"[2/2] Per-account summary -> {ACCOUNT_CSV} ({len(all_summary)} rows)")

    print("\n===== Account Comparison Summary =====")
    print(f"  {'account':<14}{'followers':>10}{'avg_eng_rate%':>15}{'posts/month':>13}")


if __name__ == "__main__":
    main()