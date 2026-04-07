#!/usr/bin/env python3
"""
scraper.py — Eric's Footy Site
Sources:
  - BBC Sport Football (RSS via feedparser) — replaces OneFootball/Reuters
  - Fotmob (Playwright headless scraper)

SOP:      architecture/scraper_sop.md
Verified: 2026-04-02 (Phase 2 handshake + source swap)
"""

import asyncio
import hashlib
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

import feedparser
from bs4 import BeautifulSoup
from dateutil import parser as dateparser
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

# ─── Paths ────────────────────────────────────────────────────────────────────
ROOT        = Path(__file__).parent.parent
DATA_DIR    = ROOT / "data"
OUTPUT_FILE = DATA_DIR / "articles.json"

# ─── Constants ────────────────────────────────────────────────────────────────
CUTOFF_HOURS   = 24
PAGE_TIMEOUT   = 45_000
WAIT_TIMEOUT   = 20_000
HYDRATION_WAIT = 2_500

BBC_RSS_URL  = "https://feeds.bbci.co.uk/sport/football/rss.xml"
FOTMOB_URL   = "https://www.fotmob.com/news"
FOTMOB_WAIT  = "a[href*='/news/']"


# ─── Utilities ────────────────────────────────────────────────────────────────

def make_id(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]

def now_utc() -> datetime:
    return datetime.now(timezone.utc)

def cutoff_time() -> datetime:
    return now_utc() - timedelta(hours=CUTOFF_HOURS)

def resolve_url(href: str, base: str) -> str:
    return href if href.startswith("http") else urljoin(base, href)

def parse_dt(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    try:
        dt = dateparser.parse(raw, fuzzy=True)
        if dt is None:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None

def clean_image_url(url: Optional[str]) -> Optional[str]:
    """Filter out data URIs and placeholder images."""
    if not url:
        return None
    if url.startswith("data:") or len(url) < 12:
        return None
    return url


# ─── BBC Sport RSS Parser ─────────────────────────────────────────────────────

def fetch_bbc_sport(cutoff: datetime) -> list[dict]:
    """
    Parse BBC Sport Football RSS feed using feedparser.
    RSS provides clean timestamps — no fallback needed.
    """
    print(f"  🌐 Fetching BBC Sport RSS: {BBC_RSS_URL}")
    articles = []

    try:
        feed = feedparser.parse(BBC_RSS_URL)
    except Exception as e:
        print(f"  ❌ BBC Sport RSS parse error: {e}", file=sys.stderr)
        return []

    if feed.bozo and not feed.entries:
        print(f"  ❌ BBC Sport RSS: malformed feed — {feed.bozo_exception}", file=sys.stderr)
        return []

    print(f"  📡 BBC Sport: {len(feed.entries)} entries in feed")

    for entry in feed.entries:
        try:
            url   = entry.get("link", "")
            title = entry.get("title", "").strip()

            if not url or not title or len(title) < 5:
                continue

            # Timestamp — RSS feeds have reliable pub dates
            pub_raw = entry.get("published") or entry.get("updated")
            published_at = parse_dt(pub_raw)

            if published_at and published_at < cutoff:
                continue  # older than 24h
            if not published_at:
                published_at = now_utc()

            # Image — from media:thumbnail or enclosure
            image_url = None
            if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
                image_url = entry.media_thumbnail[0].get("url")
            elif hasattr(entry, "enclosures") and entry.enclosures:
                for enc in entry.enclosures:
                    if enc.get("type", "").startswith("image/"):
                        image_url = enc.get("href") or enc.get("url")
                        break
            # Fallback: check tags / content
            if not image_url and hasattr(entry, "summary"):
                img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', entry.summary or "")
                if img_match:
                    image_url = img_match.group(1)

            image_url = clean_image_url(image_url)

            # Summary — strip HTML tags from description
            summary_raw = entry.get("summary") or entry.get("description") or ""
            summary = re.sub(r"<[^>]+>", "", summary_raw).strip() or None

            articles.append({
                "id":           make_id(url),
                "title":        title,
                "summary":      summary,
                "url":          url,
                "image_url":    image_url,
                "published_at": published_at.isoformat(),
                "source":       "bbc_sport",
                "saved":        False,
            })

        except Exception as e:
            print(f"  ⚠️  BBC entry error: {e}", file=sys.stderr)
            continue

    print(f"  ✅ BBC Sport: {len(articles)} articles within 24h")
    return articles


# ─── Fotmob Playwright Parser ─────────────────────────────────────────────────

def parse_fotmob(html: str, cutoff: datetime) -> list[dict]:
    """
    Strategy: a[href*='/news/'] — confirmed 14 articles in Phase 2 handshake.
    """
    soup = BeautifulSoup(html, "html.parser")
    articles = []
    seen: set[str] = set()

    for link in soup.select("a[href*='/news/']"):
        try:
            href = link.get("href", "")
            if not href:
                continue

            url = resolve_url(href, FOTMOB_URL)
            # Normalize: /embed/news/ → /news/
            url = url.replace("/embed/news/", "/news/")
            if url in seen:
                continue
            seen.add(url)

            # Title
            title_el = (
                link.find(["h1", "h2", "h3", "h4"])
                or link.find(class_=re.compile(r"title|headline", re.I))
            )
            title = (title_el.get_text(strip=True) if title_el
                     else link.get_text(strip=True)).strip()

            if not title or len(title) < 8:
                continue

            # Filter generic navigation text
            SKIP_TITLES = {"see more", "read more", "load more", "show more", "view more", "more news"}
            if title.lower().strip() in SKIP_TITLES:
                continue

            # Timestamp fallback chain
            published_at = _find_timestamp(link, url)
            if published_at and published_at < cutoff:
                continue
            if not published_at:
                published_at = now_utc()

            # Image
            img_el = link.find("img")
            image_url = clean_image_url(
                img_el.get("src") or img_el.get("data-src") if img_el else None
            )

            # Summary
            p_el = link.find("p")
            summary = p_el.get_text(strip=True) if p_el else None

            articles.append({
                "id":           make_id(url),
                "title":        title,
                "summary":      summary,
                "url":          url,
                "image_url":    image_url,
                "published_at": published_at.isoformat(),
                "source":       "fotmob",
                "saved":        False,
            })

        except Exception as e:
            print(f"  ⚠️  Fotmob parse error: {e}", file=sys.stderr)
            continue

    return articles


def _find_timestamp(container, url: str) -> Optional[datetime]:
    """Timestamp fallback chain per scraper_sop.md."""
    # 1. <time> tag
    time_el = container.find("time")
    if time_el:
        dt = parse_dt(time_el.get("datetime") or time_el.get_text(strip=True))
        if dt:
            return dt

    # 2. Class-based date elements
    for el in container.find_all(class_=re.compile(r"date|time|ago|published|timestamp|when", re.I)):
        dt = parse_dt(el.get_text(strip=True))
        if dt:
            return dt

    # 3. URL slug date pattern
    for pattern in [r"/(\d{4})/(\d{2})/(\d{2})/", r"-(\d{4})(\d{2})(\d{2})-"]:
        m = re.search(pattern, url)
        if m:
            try:
                return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc)
            except ValueError:
                continue

    return None


# ─── Playwright Fetcher ───────────────────────────────────────────────────────

async def fetch_fotmob_html(browser) -> Optional[str]:
    print(f"  🌐 Fetching Fotmob: {FOTMOB_URL}")
    page = await browser.new_page(user_agent=(
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ))
    try:
        await page.goto(FOTMOB_URL, timeout=PAGE_TIMEOUT, wait_until="domcontentloaded")
        try:
            await page.wait_for_selector(FOTMOB_WAIT, timeout=WAIT_TIMEOUT)
        except PlaywrightTimeout:
            print("  ⚠️  Fotmob: selector timeout — using current DOM")
        await page.wait_for_timeout(HYDRATION_WAIT)
        return await page.content()
    except PlaywrightTimeout:
        print("  ❌ Fotmob: page load timeout", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  ❌ Fotmob: {e}", file=sys.stderr)
        return None
    finally:
        await page.close()


# ─── Main ─────────────────────────────────────────────────────────────────────

async def run_scraper() -> dict:
    cutoff      = cutoff_time()
    scrape_start = now_utc()
    print(f"\n⚽  Scraper started — cutoff: {cutoff.strftime('%Y-%m-%d %H:%M UTC')}")

    all_articles: list[dict] = []

    # ── BBC Sport (RSS — no browser needed) ──────────────────────────────────
    bbc_articles = fetch_bbc_sport(cutoff)
    all_articles.extend(bbc_articles)

    # ── Fotmob (Playwright) ───────────────────────────────────────────────────
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            html = await fetch_fotmob_html(browser)
            if html:
                fotmob_articles = parse_fotmob(html, cutoff)
                print(f"  ✅ Fotmob: {len(fotmob_articles)} articles")
                all_articles.extend(fotmob_articles)
            else:
                print("  ⏭️  Fotmob skipped (no HTML)")
        finally:
            await browser.close()

    # Deduplicate
    seen: set[str] = set()
    deduped = []
    for a in all_articles:
        if a["id"] not in seen:
            seen.add(a["id"])
            deduped.append(a)

    # Sort newest first
    deduped.sort(key=lambda a: a["published_at"], reverse=True)

    payload = {
        "last_updated": scrape_start.isoformat(),
        "total_count":  len(deduped),
        "articles":     deduped,
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"\n🎉 Done — {len(deduped)} total articles → {OUTPUT_FILE}")
    return payload


if __name__ == "__main__":
    asyncio.run(run_scraper())
