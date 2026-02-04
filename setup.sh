#!/bin/bash
# Setup script for Pendo Feasibility Scraper
set -e

echo "=== Pendo Feasibility Scraper Setup ==="

# Detect Python
if command -v python3 &> /dev/null; then
    PYTHON=$(command -v python3)
elif command -v python &> /dev/null; then
    PYTHON=$(command -v python)
else
    echo "Error: Python not found. Install Python 3.10+ first."
    exit 1
fi

PY_VERSION=$($PYTHON --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
echo "Found Python $PY_VERSION at $PYTHON"

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    $PYTHON -m venv venv
else
    echo "Virtual environment already exists."
fi

# Activate venv
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
python -m pip install --upgrade pip

# Install Python deps
echo "Installing Python dependencies..."
python -m pip install -r requirements.txt

# Install Playwright browsers
echo "Installing Playwright Chromium..."
python -m playwright install chromium

# Create .env if not exists
if [ ! -f ".env" ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo ">>> Edit .env with your Google OAuth credentials."
else
    echo ".env already exists."
fi

# Check for Node.js
if command -v npm &> /dev/null; then
    echo "Installing web UI dependencies..."
    cd web && npm install && cd ..
else
    echo "Warning: npm not found. Skipping web UI deps."
    echo "Install Node.js if you want the web UI."
fi

echo ""
echo "=== Setup complete ==="
echo ""
echo "To activate the virtual environment:"
echo "  source venv/bin/activate"
echo ""
echo "To run CLI only:"
echo "  python pendo_feasibility_scraper.py https://example.com"
echo ""
echo "To run full stack (requires Redis):"
echo "  make run-api      # Terminal 1"
echo "  make run-worker   # Terminal 2"
echo "  make run-web      # Terminal 3 (optional)"
