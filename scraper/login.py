"""Login handling for various authentication modes."""

import logging
import time

from playwright.sync_api import Page

from .models import ScrapeConfig

log = logging.getLogger(__name__)


def apply_login(page: Page, config: ScrapeConfig, login_event=None) -> None:
    """Handle login based on config.

    Args:
        page: The Playwright page instance.
        config: Scrape configuration containing login settings.
        login_event: Optional threading.Event. When provided (UI mode),
            the function waits on the event instead of blocking on input().
    """
    if config.login_mode == 'manual':
        if login_event is not None:
            # UI mode – wait for the frontend to signal "continue".
            login_event.wait()
            return
        # CLI mode – block on stdin.
        print('\n' + '=' * 40)
        print('MANUAL LOGIN PAUSE')
        print('=' * 40)
        print('If login required:')
        print('  1. Log in to the application')
        print('  2. Navigate to main dashboard')
        print('  3. Press Enter here to continue')
        print('')
        input('Press Enter when ready...')
        return

    if config.login_mode == 'storage_state':
        if config.storage_state_path:
            return
        raise ValueError('storage_state_path required for storage_state login mode')

    if config.login_mode == 'credentials':
        if not all([config.username, config.password, config.username_selector, config.password_selector]):
            raise ValueError('Missing credentials or selectors for credential login')
        if config.login_url:
            page.goto(config.login_url, wait_until=config.wait_until, timeout=config.navigation_timeout_ms)
        page.fill(config.username_selector, config.username)
        page.fill(config.password_selector, config.password)
        if config.submit_selector:
            page.click(config.submit_selector)
        else:
            page.keyboard.press('Enter')
        time.sleep(1)
        return

    raise ValueError(f'Unknown login mode: {config.login_mode}')
