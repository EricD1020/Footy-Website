# 📋 Scraper SOP — Layer 1 Architecture

> **Golden Rule:** If this logic changes, update this SOP **before** touching `tools/scraper.py`.

---

## 🎯 Goal

Scrape football news articles published in the **last 24 hours** from:
1. **OneFootball** (`onefootball.com/en-gb/news`)
2. **Fotmob** (`fotmob.com/news`)

Merge, deduplicate, and write to `data/articles.json`.

---

## 🔧 Tech Stack

| Tool | Purpose |
|------|---------|
| `playwright` (async) | Headless Chromium — required for JS-rendered SPAs |
| `beautifulsoup4` | HTML parsing after page load |
| `hashlib` (stdlib) | SHA256 ID generation from URL |
| `dateutil.parser` | Robust ISO8601 timestamp parsing |

---

## 📐 Input / Output

**No external input required.** Script runs standalone.

**Output:** `data/articles.json`
```json
{
  "last_updated": "ISO8601",
  "total_count": 42,
  "articles": [{ "id", "title", "summary", "url", "image_url", "published_at", "source", "saved" }]
}
```

---

## 🕷️ Scraping Strategy (Verified 2026-04-02 — Phase 2 Handshake)

### OneFootball
- **URL:** `https://onefootball.com/en-gb/news`
- **Approach:** Playwright loads page, waits for JS render, BS4 parses
- **Wait selector:** `[class*='title']` (confirmed present)
- **Article link strategy:** `a[href*='/en-gb/news/']` — scopes to article URLs only, avoids nav noise
  - `[class*='title']` alone returns 35 hits including nav elements ("Matches", "Teams") — DO NOT use unscoped
  - Correct: find `<a>` tags whose `href` contains `/en-gb/news/`, then extract title from within
- **Title:** `h2`, `h3`, or `[class*='title']` *within* the article link container
- **Image:** `img[src]` or `img[data-src]` within the link container
- **Published time:** ❌ No `<time>` elements found — use timestamp fallback (see below)
- **Dedup:** SHA256 of full URL

### Fotmob
- **URL:** `https://www.fotmob.com/news`
- **Approach:** Playwright loads page, waits for JS render, BS4 parses
- **Wait selector:** `a[href*='/news/']` ✅ confirmed
- **Article link strategy:** `a[href*='/news/']` — 22 links found, 10 real titles extracted
- **Title:** `h2`/`h3`/`h4` within link, or `[class*='title'/'headline']`, or fallback to link text
- **Image:** `img[src]` or `img[data-src]` within link container
- **Published time:** ❌ No `<time>` elements found — use timestamp fallback (see below)
- **Dedup:** SHA256 of full URL

### ⚠️ Timestamp Fallback Strategy (Both Sources)
Neither site renders `<time datetime="...">` elements in the list view after JS hydration.

Resolution order:
1. Try `[class*='date']`, `[class*='time']`, `[class*='ago']`, `[class*='published']` spans within the card
2. Try to extract a date from the URL slug (e.g. `/2026/04/02/` patterns)
3. **Conservative fallback:** if still no date, set `published_at = scrape_time` and **include** the article
   - Rationale: better to show an undated article than silently drop real news
   - The 24-hour filter only applies when a reliable date IS available

---

## ⚙️ Algorithm

```
1. Launch Playwright (headless Chromium)
2. For each source [OneFootball, Fotmob]:
   a. Navigate to news URL
   b. Wait for network idle (networkidle)
   c. Extract page HTML
   d. Parse with BeautifulSoup
   e. For each article element:
      - Extract title, url, image_url, published_at, summary
      - Parse published_at → UTC datetime
      - Skip if published_at < now() - 24h
      - Generate id = sha256(url)
      - Append to source article list
3. Merge all source lists → master list
4. Deduplicate by id
5. Sort by published_at descending
6. Write to data/articles.json with last_updated = now()
```

---

## ⚠️ Edge Cases

| Scenario | Handling |
|----------|---------|
| Article has no image | `image_url = null` |
| No published timestamp found | Skip article (do not guess) |
| Source times out after 30s | Log warning, continue with other source |
| No articles in last 24h | Write empty `articles: []`, do not error |
| Duplicate URLs across sources | Deduplicate by id (first-seen wins) |
| `data/` directory missing | Create it before writing |

---

## 🔧 Self-Repair Guide

If selectors break after a site redesign:
1. Run `playwright codegen onefootball.com/en-gb/news` to inspect live selectors
2. Update the selector constants at the top of `tools/scraper.py`
3. Update the "Key selectors" section in this SOP with the date of change
4. Add a row to the Maintenance Log in `gemini.md`

---

## 📦 Dependencies

```
playwright
beautifulsoup4
python-dateutil
```

Install: `pip install -r requirements.txt && playwright install chromium`
