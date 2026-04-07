# ⚽ Eric's Footy Site

A beautiful, interactive football news dashboard that scrapes the latest articles from **BBC Sport** and **Fotmob**, displays them in a premium dark-mode UI, and lets you save articles that persist across refreshes.

---

## Features

- 📰 **Live news** from BBC Sport (RSS) and Fotmob (Playwright scraper)
- 🕐 **24-hour feed** — only articles published in the last 24 hours
- ⭐ **Save articles** — bookmarks persist via `localStorage`
- 🔄 **Manual refresh** button + 24-hour auto-refresh
- 📊 **Stats strip** showing counts per source
- 🌑 **Dark-mode, responsive UI** with glassmorphism cards and smooth animations

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | HTML5, Vanilla CSS, Vanilla JS |
| Backend | Python 3 + Flask |
| Scraping | `feedparser` (BBC RSS) + Playwright (Fotmob) |
| Persistence | `localStorage` (Phase 1) → Supabase (Phase 2) |

---

## Getting Started

### 1. Install Dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

### 2. Run the Server

```bash
python tools/server.py
```

The server will automatically run the scraper on first launch if no data exists.

Open **http://localhost:5000** in your browser.

### 3. Manual Scrape (optional)

```bash
python tools/scraper.py
```

---

## Project Structure

```
├── frontend/
│   ├── index.html       # Dashboard UI
│   ├── css/styles.css   # Design system
│   └── js/app.js        # Frontend logic
├── tools/
│   ├── scraper.py       # BBC Sport + Fotmob scraper
│   └── server.py        # Flask API server
├── architecture/        # SOP docs
├── data/                # articles.json (auto-generated, not committed)
└── requirements.txt
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/articles` | Returns the current articles payload |
| `POST` | `/api/scrape` | Triggers a fresh scrape |
| `GET` | `/api/health` | Health check |

---

## Sources

| Source | Method | Status |
|--------|--------|--------|
| BBC Sport Football | RSS via `feedparser` | ✅ Active |
| Fotmob | Playwright headless browser | ✅ Active |
| OneFootball | Scraper | ❌ Retired (anti-bot) |
| Reuters | API | ❌ Retired (paid) |
