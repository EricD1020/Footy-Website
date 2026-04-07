# 📋 Server SOP — Layer 1 Architecture

> **Golden Rule:** If this logic changes, update this SOP **before** touching `tools/server.py`.

---

## 🎯 Goal

Serve the frontend dashboard and expose a REST API that the frontend uses to:
1. Fetch articles from `data/articles.json`
2. Trigger on-demand scraping

---

## 🔧 Tech Stack

| Tool | Purpose |
|------|---------|
| `Flask` | Lightweight Python HTTP server |
| `flask-cors` | Allow frontend JS to call the API |

---

## 🛣️ API Routes

| Method | Route | Description |
|--------|-------|-------------|
| `GET` | `/` | Serves `frontend/index.html` |
| `GET` | `/api/articles` | Returns `data/articles.json` as JSON |
| `POST` | `/api/scrape` | Triggers `tools/scraper.py` and returns updated articles |
| `GET` | `/static/<path>` | Serves CSS, JS, and assets |

---

## ⚙️ Server Behavior

```
1. On startup:
   - Check if data/articles.json exists
   - If not: run scraper immediately to populate it
2. GET /api/articles:
   - Read data/articles.json
   - Return JSON payload
3. POST /api/scrape:
   - Invoke tools/scraper.py as a subprocess
   - Wait for completion
   - Return updated articles payload
4. Static routes:
   - Serve /frontend/css/ and /frontend/js/ as static assets
```

---

## ⚠️ Edge Cases

| Scenario | Handling |
|----------|---------|
| `data/articles.json` missing | Return `{"articles": [], "total_count": 0}` |
| Scraper subprocess fails | Return HTTP 500 with error message |
| Port 5000 already in use | Log error and suggest `PORT=5001 python tools/server.py` |

---

## 🚀 Running the Server

```bash
python tools/server.py
# Server starts at http://localhost:5000
```

Environment variable override:
```bash
PORT=8080 python tools/server.py
```

---

## 📦 Dependencies

```
flask
flask-cors
```
