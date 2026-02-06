"""URL helpers: allow/deny filtering, extension skipping, link extraction."""

import logging
import re
from urllib.parse import urljoin, urlparse

from playwright.sync_api import Page

from .patterns import _SKIP_EXTENSIONS

log = logging.getLogger(__name__)


def url_allowed(url: str, allowlist_patterns: list, denylist_patterns: list) -> bool:
    """Check if a URL passes allow/deny patterns."""
    if denylist_patterns:
        for pattern in denylist_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return False
    if not allowlist_patterns:
        return True
    for pattern in allowlist_patterns:
        if re.search(pattern, url, re.IGNORECASE):
            return True
    return False


def _has_skip_extension(path: str) -> bool:
    """Return True if the URL path ends with a skippable file extension."""
    lower = path.lower()
    for ext in _SKIP_EXTENSIONS:
        if lower.endswith(ext):
            return True
    return False


def extract_internal_links(
    page: Page,
    base_url: str,
    max_links: int = 20,
    include_query_params: bool = False,
    allowlist_patterns: list = None,
    denylist_patterns: list = None,
) -> list:
    """Extract internal links with allow/deny rules."""
    base_domain = urlparse(base_url).netloc
    internal_links: set[str] = set()
    allowlist_patterns = allowlist_patterns or []
    denylist_patterns = denylist_patterns or []

    try:
        # Batch extraction: get all hrefs in one JS call instead of per-element.
        hrefs = page.evaluate('''
            () => {
                const links = [];
                document.querySelectorAll('a[href]').forEach(a => {
                    links.push(a.href);
                });
                return links;
            }
        ''')
    except Exception as exc:
        log.debug('Link extraction failed: %s', exc)
        return []

    for href in hrefs:
        if not href:
            continue

        full_url = urljoin(base_url, href)
        parsed = urlparse(full_url)

        if parsed.netloc != base_domain:
            continue

        if _has_skip_extension(parsed.path):
            continue

        clean_url = f'{parsed.scheme}://{parsed.netloc}{parsed.path}'
        if include_query_params and parsed.query:
            clean_url = f'{clean_url}?{parsed.query}'

        if not url_allowed(clean_url, allowlist_patterns, denylist_patterns):
            continue

        if clean_url != base_url and clean_url not in internal_links:
            internal_links.add(clean_url)
            if len(internal_links) >= max_links:
                break

    return list(internal_links)
