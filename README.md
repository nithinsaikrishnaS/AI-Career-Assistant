# 🚀 AI Career Assistant Pro

An enterprise-grade, autonomous job discovery ecosystem designed to transform how you find and apply for roles. Built for reliability, intelligence, and 24/7 production uptime.

![Dashboard Preview](assets/dashboard_preview.png) *(Note: Add your own screenshot here)*

## ✨ Key Features

- **Autonomous Discovery**: Parallel scrapers for enterprise portals (Microsoft, Amazon, Accenture, TCS, etc.) and startup platforms (Wellfound, Internshala).
- **Universal Role Intelligence**: Advanced matching engine with Title-Weighting and Domain Classification.
- **Real-Time Observability**: Live dashboard showing system health, re-scoring status, and scraper performance.
- **Instant Alerts**: Targeted Telegram notifications with interactive action buttons.
- **Profile Synchronization**: Automatic database-wide re-calculation whenever your profile is updated.

## 🏗️ Architecture

- **Backend**: FastAPI (Python 3.9+) with APScheduler for heartbeats.
- **Database**: SQLite with WAL (Write-Ahead Logging) for safe multi-worker access.
- **Discovery**: Hybrid scraping using BeautifulSoup4 and Playwright (Chromium).
- **Frontend**: Premium UI with Glassmorphism and Real-Time Telemetry.

## 🚀 Quick Start

### 1. Prerequisities
- Python 3.9+
- Linux (Ubuntu recommended for deployment)

### 2. Installation
```bash
git clone https://github.com/your-username/ai-career-assistant.git
cd ai-career-assistant
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
sudo playwright install-deps
```

### 3. Configuration
Copy `.env.template` to `.env.local` and fill in your secrets:
- `GEMINI_API_KEY`: For matching intelligence.
- `TELEGRAM_BOT_TOKEN`: From @BotFather.
- `TELEGRAM_CHAT_ID`: Your personal chat ID.

### 4. Running the App
**Development:**
```bash
python3 main.py
```
**Production:**
```bash
gunicorn main:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --workers 2
```

## 🛡️ Security
- **CSRF Protection**: Gated manual scan triggers.
- **Rate Limiting**: 60 requests/min throttle to protect infrastructure.
- **Persistence**: Atomic database commits with thread-safe writes.

## 📜 License
MIT License. Free for personal and commercial use.

---
*Created with ❤️ for high-performance career growth.*
