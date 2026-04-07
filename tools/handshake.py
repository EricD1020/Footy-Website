#!/usr/bin/env python3
"""
handshake.py — Phase 2: Link Verification
Minimal script to confirm we can reach and parse OneFootball and Fotmob.
Does NOT write any files. Prints findings to stdout only.

Pass criteria:
  - At least 1 article title found on each source
  - No timeout or connection errors
"""

import asyncio
import re
import sys
from datetime import datetime, timezone

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

SOURCES = {
    "onefootball": {
        "url": "https://onefootball.com/en-gb/news",
        "wait_for": "article",
        "wait_timeout": 15_000,
    },
    "fotmob": {
        "url": "https://www.fotmob.com/news",
        "wait_for": "a[href*='/news/']",
        "wait_timeout": 15_000,
    },
}

RESULTS = {}


async def probe_source(browser, name: str, config: dict):
    print(f"\n{'─'*50}")
    print(f"🌐 Probing: {name.upper()} → {config['url']}")
    page = await browser.new_page()

    try:
        await page.goto(config["url"], timeout=30_000, wait_until="domcontentloaded")

        try:
            await page.wait_for_selector(config["wait_for"], timeout=config["wait_timeout"])
            print(f"   ✅ Wait selector found: {config['wait_for']}")
        except PlaywrightTimeout:
            print(f"   ⚠️  Wait selector NOT found: {config['wait_for']}")

        await page.wait_for_timeout(2000)
        html = await page.content()
        soup = BeautifulSoup(html, "html.parser")

        # ── OneFootball probes ──────────────────────────────────────
        if name == "onefootball":
            titles = []

            # Try several selector strategies
            for strategy, els in [
                ("article h2/h3", soup.select("article h2, article h3")),
                ("[data-testid] h2", soup.select("[data-testid] h2")),
                ("[class*='title']", soup.select("[class*='title']")),
                ("[class*='headline']", soup.select("[class*='headline']")),
                ("[class*='ArticleCard'] h2", soup.select("[class*='ArticleCard'] h2")),
            ]:
                if els:
                    texts = [e.get_text(strip=True) for e in els if e.get_text(strip=True)]
                    if texts:
                        print(f"   📌 Strategy '{strategy}' → {len(texts)} titles")
                        for t in texts[:3]:
                            print(f"      • {t[:80]}")
                        titles = texts
                        RESULTS[name] = {"strategy": strategy, "count": len(texts), "sample": texts[:3]}
                        break

            if not titles:
                print(f"   ❌ No titles found with any strategy")
                # Dump available top-level element classes to help debug
                classes = set()
                for el in soup.find_all(True, limit=100):
                    if el.get("class"):
                        classes.update(el["class"])
                print(f"   🔍 Sample classes on page: {list(classes)[:15]}")
                RESULTS[name] = {"strategy": None, "count": 0, "sample": []}

            # Check for time elements
            times = soup.find_all("time")
            print(f"   ⏱  <time> elements found: {len(times)}")
            if times:
                print(f"      First: {times[0]}")

        # ── Fotmob probes ──────────────────────────────────────────
        elif name == "fotmob":
            links = soup.select("a[href*='/news/']")
            titles = []

            for link in links[:10]:
                title_el = (
                    link.find(["h2", "h3", "h4"])
                    or link.find(class_=re.compile(r"title|headline", re.I))
                )
                text = title_el.get_text(strip=True) if title_el else link.get_text(strip=True)
                if text and len(text) > 5:
                    titles.append(text)

            print(f"   📌 a[href*='/news/'] links: {len(links)}")
            print(f"   📌 Titles extracted: {len(titles)}")
            for t in titles[:3]:
                print(f"      • {t[:80]}")

            RESULTS[name] = {"strategy": "a[href*='/news/']", "count": len(titles), "sample": titles[:3]}

            times = soup.find_all("time")
            print(f"   ⏱  <time> elements found: {len(times)}")

    except PlaywrightTimeout:
        print(f"   ❌ Page load timed out")
        RESULTS[name] = {"strategy": None, "count": 0, "error": "timeout"}
    except Exception as e:
        print(f"   ❌ Error: {e}")
        RESULTS[name] = {"strategy": None, "count": 0, "error": str(e)}
    finally:
        await page.close()


async def main():
    print(f"\n⚽  HANDSHAKE — Phase 2: Link Verification")
    print(f"   Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*50}")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            for name, config in SOURCES.items():
                await probe_source(browser, name, config)
        finally:
            await browser.close()

    # ── Summary ──────────────────────────────────────────────────────────────
    print(f"\n{'='*50}")
    print("📊 HANDSHAKE SUMMARY")
    print(f"{'='*50}")

    all_pass = True
    for name, result in RESULTS.items():
        count = result.get("count", 0)
        strategy = result.get("strategy", "none")
        status = "✅ PASS" if count > 0 else "❌ FAIL"
        if count == 0:
            all_pass = False
        print(f"  {status}  {name:<16} | {count} articles | selector: {strategy}")

    print(f"\n{'─'*50}")
    if all_pass:
        print("🟢 ALL SOURCES CONNECTED — Phase 2: Link PASSED")
        print("   → Safe to proceed to Phase 3: Architect")
    else:
        print("🔴 ONE OR MORE SOURCES FAILED — selectors need updating")
        print("   → Fix selectors in scraper_sop.md + scraper.py before proceeding")
    print(f"{'─'*50}\n")

    return 0 if all_pass else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
