# 🔍 Findings — Eric's Footy Site

> Research, discoveries, constraints, API quirks, and integration notes.

---

## 📅 2026-04-01

### Initial Survey
- Workspace initialized at `/Users/ericdiaz/Downloads/erics footy site`
- Directory was empty — clean slate project
- Discovery questions sent to user — awaiting responses

---

## 📅 2026-04-02 — Phase 2: Link Results

### ✅ OneFootball (`onefootball.com/en-gb/news`)
- `article` selector: ❌ not found (likely using custom components)
- `[class*='title']` selector: ✅ 35 hits BUT includes nav noise ("Matches", "Teams", "Competitions")
- **Action needed**: Scope selector tighter — pair with a parent container class to exclude nav
- `<time>` elements: ❌ 0 found — dates rendered differently (likely JS-injected spans)

### ✅ Fotmob (`fotmob.com/news`)
- `a[href*='/news/']` selector: ✅ 22 links, 10 real article titles extracted successfully
- Sample titles confirmed real: "Four Potential Pep Guardiola Replacements at Man City—Ranked"
- `<time>` elements: ❌ 0 found

### ⚠️ Timestamp Strategy (Both Sources)
- Neither source uses standard `<time datetime="...">` elements after JS render
- Strategy for Phase 3: Look for `[class*='date']`, `[class*='time']`, `[class*='ago']` spans
- Fallback: Use article's metadata from URL slug (some contain dates) or default to scrape time
- For 24-hr filtering: if we can't parse pub date, include article (conservative — better than missing real news)

---

## 📅 2026-04-02 — Source Change: OneFootball → Reuters → BBC Sport

### ❌ OneFootball — BLOCKED
- `a[href*='/en-gb/news/']` yields 0 results — article content never loads in headless browser
- Likely requires login or heavy anti-bot (JS challenges, geo-gating)

### ❌ Reuters — BLOCKED (HTTP 401)
- `https://www.reuters.com/sports/soccer/` returns 401 Unauthorized
- All RSS feeds at `feeds.reuters.com` are dead/decommissioned
- Reuters content requires a paid API subscription — not viable

### ✅ BBC Sport Football RSS — LIVE
- `https://feeds.bbci.co.uk/sport/football/rss.xml`
- HTTP 200, XML RSS feed, real articles confirmed
- Sample: "De Zerbi apologises to fans for Greenwood comments"
- No scraping needed — pure RSS parsing with `feedparser`

### ✅ Guardian Football RSS — LIVE (backup)
- `https://www.theguardian.com/football/rss`
- HTTP 200, XML RSS feed, real articles confirmed

### ✅ ESPN Soccer RSS — LIVE (backup, US-focused)
- `https://www.espn.com/espn/rss/soccer/news`

### 📌 Decision
- Replacing OneFootball + Reuters with **BBC Sport Football RSS**
- Keeping **Fotmob** (Playwright scraper, 14 articles confirmed)
- Updated in `gemini.md`

---

## 🔗 External Resources

> _To be populated after Discovery Questions answered._

---

## ⚠️ Constraints & Gotchas

> _To be populated as discovered._

---

## 🧪 API Notes

> _To be populated during Link phase._
