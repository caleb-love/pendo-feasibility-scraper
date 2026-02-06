"""Page interaction helpers: scrolling, popup dismissal, page analysis orchestration."""

import logging
import time

from playwright.sync_api import Page

from .models import PageAnalysis
from .analysis import (
    analyse_element,
    analyse_dynamic_classes,
    analyse_iframes,
    detect_shadow_dom,
    analyse_canvas,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# JS snippets
# ---------------------------------------------------------------------------

_SCROLL_JS = '''
async () => {
    await new Promise(resolve => {
        let totalHeight = 0;
        const distance = 300;
        const timer = setInterval(() => {
            window.scrollBy(0, distance);
            totalHeight += distance;
            if (totalHeight >= document.body.scrollHeight || totalHeight > 5000) {
                clearInterval(timer);
                window.scrollTo(0, 0);
                resolve();
            }
        }, 100);
    });
}
'''

_POPUP_SELECTORS = [
    'button:has-text("Accept")',
    'button:has-text("Accept All")',
    'button:has-text("Got it")',
    '[aria-label="Close"]',
]


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def scroll_page(page: Page) -> None:
    """Scroll to trigger lazy loading."""
    try:
        page.evaluate(_SCROLL_JS)
    except Exception as exc:
        log.debug('Scroll failed: %s', exc)


def dismiss_popups(page: Page) -> None:
    """Dismiss common popups (cookie banners, welcome dialogs, etc.)."""
    for selector in _POPUP_SELECTORS:
        try:
            button = page.query_selector(selector)
            if button and button.is_visible():
                button.click()
                time.sleep(0.3)
        except Exception as exc:
            log.debug('Popup dismissal failed for %s: %s', selector, exc)


def analyse_page(page: Page, url: str, should_scroll: bool = True) -> PageAnalysis:
    """Run full analysis on a single page."""
    analysis = PageAnalysis(url=url)

    if should_scroll:
        scroll_page(page)
        time.sleep(0.5)

    analyse_element(page, 'button', analysis.buttons)
    analyse_element(page, 'input', analysis.inputs)
    analyse_element(page, 'a', analysis.links)

    dynamic_count, dynamic_examples = analyse_dynamic_classes(page)
    analysis.dynamic_class_count = dynamic_count
    analysis.dynamic_class_examples = dynamic_examples

    analysis.iframes = analyse_iframes(page, url)
    analysis.shadow_dom = detect_shadow_dom(page, url)
    analysis.canvas = analyse_canvas(page, url)

    return analysis
