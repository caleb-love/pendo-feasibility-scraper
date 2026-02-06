#!/usr/bin/env python3
"""
Pendo Feasibility Scraper v5
Analyses a website for Pendo tagging compatibility.
Aligned with Pendo's CSS selector best practices.
Requires: pip install playwright && playwright install chromium

This module is the public entry-point and CLI.  All core logic lives in the
``scraper`` package (scraper/models.py, scraper/patterns.py, etc.) and is
re-exported here so existing imports remain unchanged:

    from pendo_feasibility_scraper import run_scan, ScrapeConfig
"""

import json
import logging
import sys
from datetime import datetime
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Logging (configured at module level for both CLI and UI modes)
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s',
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Re-export every public symbol from the scraper package so all existing
# imports like ``from pendo_feasibility_scraper import ScrapeConfig`` still
# work after the split.
# ---------------------------------------------------------------------------
from scraper import (  # noqa: F401, E402
    # Models
    SelectorSuggestion,
    ElementAnalysis,
    IframeInfo,
    ShadowDOMInfo,
    CanvasInfo,
    SoftwareDetection,
    PageAnalysis,
    ScrapeConfig,
    ScanResult,
    # Patterns
    DYNAMIC_ID_PATTERNS,
    DYNAMIC_CLASS_PATTERNS,
    SOFTWARE_SIGNATURES,
    check_dynamic_id,
    check_dynamic_class,
    # Analysis
    suggest_selector,
    analyse_element,
    analyse_dynamic_classes,
    detect_software,
    analyse_iframes,
    detect_shadow_dom,
    analyse_canvas,
    # URL utilities
    url_allowed,
    extract_internal_links,
    # Page helpers
    scroll_page,
    dismiss_popups,
    analyse_page,
    # Reporting
    get_short_url,
    generate_report,
    generate_json_report,
    # Login
    apply_login,
    # Scanner
    run_scan,
)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    """CLI entry point.

    No arguments  -> launches the local Apple II web UI.
    With URL arg  -> runs a headless CLI scan (original behaviour).
    """
    if len(sys.argv) < 2:
        # Launch local UI mode.
        from local_ui import launch  # noqa: lazy import to avoid circular deps
        launch()
        return

    start_url = sys.argv[1]

    print(f'\nPendo Feasibility Scraper v5')
    print(f'Target: {start_url}')
    print('-' * 40)

    config = ScrapeConfig(
        headless=False,
        login_mode='manual',
    )

    log.info('Navigating to %s ...', start_url)
    result = run_scan(start_url, config)

    print('\n' + result.report_text)

    domain = urlparse(result.start_url).netloc.replace('.', '_').replace(':', '_')
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'pendo_feasibility_{domain}_{timestamp}.txt'
    json_filename = f'pendo_feasibility_{domain}_{timestamp}.json'

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(result.report_text)
    with open(json_filename, 'w', encoding='utf-8') as f:
        json.dump(result.report_json, f, indent=2)

    log.info('Report saved to: %s', filename)
    log.info('JSON saved to: %s', json_filename)


if __name__ == '__main__':
    main()
