.PHONY: setup install run-cli run-api run-worker run-web clean

# Default Python in venv
PYTHON := venv/bin/python
PIP := venv/bin/pip

setup:
	@./setup.sh

install: setup

run-cli:
	@$(PYTHON) pendo_feasibility_scraper.py $(URL)

run-api:
	@$(PYTHON) -m uvicorn server.app:app --reload --port 8000

run-worker:
	@$(PYTHON) -m worker.worker

run-web:
	@cd web && npm run dev

build-web:
	@cd web && npm run build

clean:
	rm -rf venv
	rm -rf web/node_modules
	rm -rf web/dist
	rm -rf data
	rm -rf __pycache__
	rm -rf server/__pycache__
	rm -rf worker/__pycache__

help:
	@echo "Pendo Feasibility Scraper"
	@echo ""
	@echo "Usage:"
	@echo "  make setup         - Create venv and install all deps"
	@echo "  make run-cli URL=https://example.com - Run CLI scan"
	@echo "  make run-api       - Start API server (port 8000)"
	@echo "  make run-worker    - Start background worker"
	@echo "  make run-web       - Start web UI dev server"
	@echo "  make build-web     - Build web UI for production"
	@echo "  make clean         - Remove venv and build artifacts"
