"""Scan orchestrator: drives the full multi-page scrape and produces reports."""

import logging
import time

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

from .models import ScrapeConfig, ScanResult
from .analysis import detect_software
from .page_helpers import dismiss_popups, analyse_page
from .url_utils import extract_internal_links
from .login import apply_login
from .reporting import generate_report, generate_json_report

log = logging.getLogger(__name__)


def run_scan(
    start_url: str,
    config: ScrapeConfig,
    progress_callback=None,
    login_event=None,
) -> ScanResult:
    """Run a full scan and return structured results.

    Args:
        start_url: The URL to begin crawling from.
        config: Scrape configuration.
        progress_callback: Optional callable(str). Called with human-readable
            progress messages so a UI can display live status.
        login_event: Optional threading.Event. Passed to apply_login so the
            UI can signal "continue" instead of blocking on stdin.
    """
    _progress = progress_callback or (lambda msg: None)

    if not start_url.startswith('http'):
        start_url = 'https://' + start_url

    with sync_playwright() as p:
        _progress('LAUNCHING BROWSER...')
        browser = p.chromium.launch(headless=config.headless, slow_mo=config.browser_slow_mo_ms)
        context_kwargs = {'viewport': {'width': config.viewport_width, 'height': config.viewport_height}}
        if config.login_mode == 'storage_state' and config.storage_state_path:
            context_kwargs['storage_state'] = config.storage_state_path
        context = browser.new_context(**context_kwargs)
        page = context.new_page()

        _progress(f'NAVIGATING TO {start_url}')
        try:
            page.goto(start_url, wait_until=config.wait_until, timeout=config.navigation_timeout_ms)
        except PlaywrightTimeout:
            log.warning('Initial navigation timed out for %s – proceeding anyway', start_url)
            _progress('NAVIGATION TIMED OUT - PROCEEDING ANYWAY')

        if config.login_mode == 'manual':
            _progress('WAITING FOR LOGIN...')
        apply_login(page, config, login_event=login_event)
        _progress('LOGIN COMPLETE')

        current_url = page.url
        if config.dismiss_popups:
            dismiss_popups(page)
            time.sleep(1)

        _progress('DETECTING SOFTWARE...')
        log.info('Detecting software on %s', current_url)
        software = detect_software(page)

        _progress(f'ANALYSING PAGE 1: {current_url}')
        log.info('Analysing page 1: %s', current_url)
        analyses = [analyse_page(page, current_url, should_scroll=config.scroll_pages)]

        internal_links = extract_internal_links(
            page,
            current_url,
            max_links=config.max_links,
            include_query_params=config.include_query_params,
            allowlist_patterns=config.allowlist_patterns,
            denylist_patterns=config.denylist_patterns,
        )

        pages_to_crawl = min(len(internal_links), max(0, config.max_pages - 1))
        _progress(f'FOUND {len(internal_links)} INTERNAL LINKS, CRAWLING {pages_to_crawl}')

        for idx, link in enumerate(internal_links[:pages_to_crawl], start=2):
            try:
                page.goto(link, wait_until=config.wait_until, timeout=config.navigation_timeout_ms)
                time.sleep(1)
                if config.dismiss_popups:
                    dismiss_popups(page)

                _progress(f'ANALYSING PAGE {idx}/{pages_to_crawl + 1}: {link}')
                log.info('Analysing page %d/%d: %s', idx, pages_to_crawl + 1, link)
                analyses.append(analyse_page(page, link, should_scroll=config.scroll_pages))

                # Merge any newly-detected software from subsequent pages.
                page_software = detect_software(page)
                for fw in page_software.frontend_frameworks:
                    if fw not in software.frontend_frameworks:
                        software.frontend_frameworks.append(fw)
                for fw in page_software.css_frameworks:
                    if fw not in software.css_frameworks:
                        software.css_frameworks.append(fw)
                for tool in page_software.analytics_tools:
                    if tool not in software.analytics_tools:
                        software.analytics_tools.append(tool)
                for tool in page_software.other_tools:
                    if tool not in software.other_tools:
                        software.other_tools.append(tool)

            except Exception as exc:
                log.warning('Failed to analyse %s: %s', link, exc)
                _progress(f'FAILED: {link} ({exc})')
                continue
            time.sleep(0.5)

        browser.close()

    _progress('GENERATING REPORT...')
    report_text = generate_report(start_url, analyses, software)
    report_json = generate_json_report(start_url, analyses, software)
    _progress('SCAN COMPLETE')

    return ScanResult(
        start_url=start_url,
        analyses=analyses,
        software=software,
        report_text=report_text,
        report_json=report_json,
    )
