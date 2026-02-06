# Pendo Feasibility Scraper //e

Analyses a website for Pendo tagging compatibility — detects dynamic IDs, CSS-in-JS classes, shadow DOM, iframes, canvas elements, and installed software. Outputs a risk-scored feasibility report.

Ships with a retro Apple II CRT-themed local UI that launches in your browser.

## Quick Start

```bash
make start
```

That's it. On first run it creates a virtualenv, installs dependencies, installs Playwright Chromium, then opens the Apple II UI at `http://localhost:8080`.

## Features

- **One-command launch** — `make start` handles setup + server + browser open
- **Apple II CRT interface** — green phosphor text, scanlines, blinking cursor, the works
- **Real-time progress** — scan status streams line-by-line into the CRT screen
- **Manual login support** — opens a visible browser for you to log in, then click Continue in the UI
- **CLI mode** — pass a URL argument for headless terminal-only usage
- **Hosted mode** — full-stack deployment with Google OAuth, Redis queue, and React web UI
- **Comprehensive analysis:**
  - Element ID stability scoring (stable vs dynamic vs missing)
  - Dynamic CSS class detection (CSS Modules, Styled Components, Emotion, JSS, etc.)
  - `data-pendo-*` attribute detection
  - Software/framework fingerprinting (React, Next.js, Angular, Vue, MUI, Chakra, etc.)
  - Competitor analytics detection (Appcues, WalkMe, Userpilot, Chameleon)
  - Shadow DOM, iframe, and canvas element mapping
  - Risk scoring with actionable recommendations

## Usage

### Local UI (recommended)

```bash
make start
```

Opens the Apple II interface in your browser. Enter a URL, configure options, click **RUN SCAN**. The report renders on-screen with copy and JSON download buttons.

### CLI mode

```bash
# With make
make run-cli URL=https://app.example.com

# Direct
source venv/bin/activate
python pendo_feasibility_scraper.py https://app.example.com
```

Opens a visible browser for manual login, then crawls pages and saves `.txt` and `.json` reports to the current directory.

### Hosted mode (requires Redis + OAuth)

For team deployments with Google OAuth and a job queue:

```bash
# Terminal 1: API server
make run-api

# Terminal 2: Background worker
make run-worker

# Terminal 3: React web UI (development)
make run-web
```

Configure OAuth and Redis in `.env` (see `.env.example`).

## Prerequisites

- Python 3.10+
- Node.js 18+ (only for hosted mode React UI)
- Redis (only for hosted mode)

## Manual Setup

If you prefer not to use `make start`:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
cp .env.example .env
```

## Login Modes

| Mode | Description | UI Support |
|------|-------------|------------|
| `none` | No login needed — scans immediately | Yes |
| `manual` | Opens visible browser for interactive login | Yes (click Continue when done) |
| `credentials` | Auto-fills username/password via CSS selectors | Yes |
| `storage_state` | Uses a Playwright storage state JSON file | Yes |

## Configuration

### Environment Variables (hosted mode only)

| Variable | Description |
|----------|-------------|
| `GOOGLE_OAUTH_CLIENT_ID` | Google OAuth client ID |
| `GOOGLE_OAUTH_CLIENT_SECRET` | Google OAuth client secret |
| `GOOGLE_OAUTH_REDIRECT_URI` | OAuth callback URL |
| `ALLOWED_GOOGLE_DOMAIN` | Restrict login to this domain (default: `pendo.io`) |
| `SESSION_SECRET` | Session encryption key |
| `REDIS_URL` | Redis connection URL |

### Scan Options

| Option | Default | Description |
|--------|---------|-------------|
| Max Pages | 12 | Number of internal pages to crawl |
| Headless | true | Run browser invisibly |
| Dismiss Popups | true | Auto-close cookie banners |
| Scroll Pages | true | Scroll to trigger lazy loading |

## Project Structure

```
pendo_feasibility_scraper.py  — Core scraper engine + CLI entry point
local_ui.py                   — Local Apple II web UI server
server/                       — Hosted FastAPI API (OAuth, queue)
worker/                       — Redis background worker
web/                          — React frontend (hosted mode)
tests/                        — Test suite
deploy/                       — Dockerfiles + Render config
```

## Deployment

Use `deploy/Dockerfile.api` and `deploy/Dockerfile.worker` for containerised deployment. A sample `deploy/render.yaml` is included for Render.

## Make Targets

```
make start       — Launch local UI (auto-setup if needed)
make setup       — Create venv and install all deps
make run-cli     — Run CLI scan (URL=https://...)
make run-api     — Start hosted API server (port 8000)
make run-worker  — Start background worker
make run-web     — Start React dev server
make build-web   — Build React UI for production
make clean       — Remove venv and build artifacts
```
