# Pendo Feasibility Scraper

Hosted UI + API + worker for analyzing Pendo tagging feasibility across B2B SaaS apps.

## Features
- Google OAuth login restricted to a Pendo domain
- Web UI for submitting scans and viewing reports
- Background worker running Playwright
- Text and JSON report outputs
- CLI mode still supported

## Quick Start

### One-command setup
```bash
./setup.sh
```
This creates a virtual environment, installs all Python and Node dependencies, and sets up Playwright.

### Activate the environment
```bash
source venv/bin/activate
```

### CLI usage (no Redis needed)
```bash
python pendo_feasibility_scraper.py https://app.example.com
# or
make run-cli URL=https://app.example.com
```

### Full stack (requires Redis)
```bash
# Terminal 1: API server
make run-api

# Terminal 2: Background worker
make run-worker

# Terminal 3: Web UI (optional, for development)
make run-web
```

## Prerequisites
- Python 3.10+
- Node.js 18+ (for web UI)
- Redis (for full stack mode only)

## Manual setup (alternative)
If you prefer not to use the setup script:
```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
python -m playwright install chromium
cp .env.example .env
cd web && npm install && cd ..
```

## OAuth settings
- Redirect URI must match `GOOGLE_OAUTH_REDIRECT_URI` (e.g. `http://localhost:8000/auth/callback`)
- Domain access controlled with `ALLOWED_GOOGLE_DOMAIN`

## Login modes
- `manual`: pauses for interactive login (CLI only)
- `credentials`: form selectors + username/password
- `storage_state`: Playwright storage state path

## CLI usage
`python pendo_feasibility_scraper.py https://app.example.com`

## Deployment
Use `deploy/Dockerfile.api` and `deploy/Dockerfile.worker`. A sample `deploy/render.yaml` is included.
