#!/usr/bin/env python3
"""
Pendo Feasibility Scraper v5
Analyses a website for Pendo tagging compatibility.
Aligned with Pendo's CSS selector best practices.
Requires: pip install playwright && playwright install chromium
"""

import json
import logging
import re
import sys
import time
from datetime import datetime
from urllib.parse import urljoin, urlparse
from dataclasses import dataclass, field
from typing import Optional
from playwright.sync_api import sync_playwright, Page, TimeoutError as PlaywrightTimeout

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s',
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ElementAnalysis:
    """Stores analysis for a single element type."""
    total: int = 0
    stable_ids: int = 0
    dynamic_ids: int = 0
    no_ids: int = 0
    has_pendo_attr: int = 0
    has_data_attr: int = 0
    has_text_content: int = 0
    dynamic_id_examples: list = field(default_factory=list)
    stable_id_examples: list = field(default_factory=list)
    pendo_attr_examples: list = field(default_factory=list)
    dynamic_class_examples: list = field(default_factory=list)


@dataclass
class IframeInfo:
    """Info about an iframe found on a page."""
    src: str
    page_url: str
    is_cross_origin: bool


@dataclass
class ShadowDOMInfo:
    """Info about shadow DOM found on a page."""
    count: int
    page_url: str
    element_tags: list = field(default_factory=list)


@dataclass
class CanvasInfo:
    """Info about canvas elements found on a page."""
    count: int
    page_url: str
    dimensions: list = field(default_factory=list)


@dataclass
class SoftwareDetection:
    """Detected software and frameworks."""
    frontend_frameworks: list = field(default_factory=list)
    css_frameworks: list = field(default_factory=list)
    analytics_tools: list = field(default_factory=list)
    other_tools: list = field(default_factory=list)
    meta_generator: str = ''


@dataclass
class PageAnalysis:
    """Stores analysis for a single page."""
    url: str
    buttons: ElementAnalysis = field(default_factory=ElementAnalysis)
    inputs: ElementAnalysis = field(default_factory=ElementAnalysis)
    links: ElementAnalysis = field(default_factory=ElementAnalysis)
    dynamic_class_count: int = 0
    dynamic_class_examples: list = field(default_factory=list)
    iframes: list = field(default_factory=list)
    shadow_dom: Optional[ShadowDOMInfo] = None
    canvas: Optional[CanvasInfo] = None


@dataclass
class ScrapeConfig:
    """Config for running a scan."""
    max_links: int = 20
    max_pages: int = 12
    headless: bool = True
    viewport_width: int = 1920
    viewport_height: int = 1080
    wait_until: str = 'domcontentloaded'
    navigation_timeout_ms: int = 30000
    include_query_params: bool = False
    allowlist_patterns: list = field(default_factory=list)
    denylist_patterns: list = field(default_factory=list)
    login_mode: str = 'manual'  # manual|credentials|storage_state
    login_url: str = ''
    username_selector: str = ''
    password_selector: str = ''
    submit_selector: str = ''
    username: str = ''
    password: str = ''
    storage_state_path: str = ''
    dismiss_popups: bool = True
    scroll_pages: bool = True
    browser_slow_mo_ms: int = 0


@dataclass
class ScanResult:
    """Results for a scan run."""
    start_url: str
    analyses: list
    software: SoftwareDetection
    report_text: str
    report_json: dict


# ---------------------------------------------------------------------------
# Pre-compiled pattern tables
# ---------------------------------------------------------------------------

# Dynamic ID patterns – these are PROBLEMATIC for Pendo.
# Each entry: (compiled_regex, label, reason, has_stable_prefix)
_DYNAMIC_ID_PATTERNS_RAW = [
    # Framework auto-generated (no stable prefix)
    (r'^ember\d+$', 'ember*', 'Ember.js runtime ID - changes each page load', False),
    (r'^:r[a-z0-9]+:$', 'radix-:r*:', 'Radix UI runtime ID - changes each render', False),
    (r'^\d+$', 'numeric-only', 'Database record ID - changes per item', False),
    # Framework patterns WITH stable prefix (starts-with workaround possible)
    (r'^react-select-\d+-', 'react-select-*', 'React Select instance ID', True),
    (r'^mui-\d+', 'mui-*', 'Material UI component ID', True),
    (r'^radix-[a-z]+-', 'radix-*', 'Radix UI component', True),
    (r'^headlessui-[a-z]+-', 'headlessui-*', 'Headless UI component', True),
    (r'^downshift-\d+-', 'downshift-*', 'Downshift component', True),
    (r'^chakra-[a-z]+-', 'chakra-*', 'Chakra UI component', True),
    (r'^mantine-[a-z]+-', 'mantine-*', 'Mantine UI component', True),
    # Angular patterns
    (r'^ng-c\d+$', 'ng-c*', 'Angular compiler ID - changes on rebuild', False),
    (r'^cdk-[a-z]+-\d+', 'cdk-*', 'Angular CDK component', True),
    (r'^mat-[a-z]+-\d+', 'mat-*', 'Angular Material component', True),
    # Hash-based patterns
    (r'^[a-f0-9]{8}-[a-f0-9]{4}-', 'uuid-*', 'UUID - generated per session', False),
    (r'^[a-f0-9]{12,}$', 'hash-only', 'Pure hash ID - changes on rebuild', False),
    (r'^[a-z]{1,2}\d{5,}$', 'minified', 'Minified ID - changes on rebuild', False),
    # Suffix patterns
    (r'^([a-z][-a-z]+)[-_][a-f0-9]{5,}$', '*-hash', 'Hash suffix on class name', True),
    (r'^([a-z][-a-z]+)__[a-zA-Z0-9]{5,}$', '*__hash', 'CSS Modules hash suffix', True),
    # CSS-in-JS generated IDs
    (r'^(sc|css|emotion|styled)-[a-zA-Z0-9]+$', 'css-in-js', 'CSS-in-JS generated ID', True),
]

DYNAMIC_ID_PATTERNS = [
    (re.compile(pattern, re.IGNORECASE), label, reason, has_prefix)
    for pattern, label, reason, has_prefix in _DYNAMIC_ID_PATTERNS_RAW
]

# Dynamic CLASS patterns
_DYNAMIC_CLASS_PATTERNS_RAW = [
    # Hash suffix patterns like button-7234523bfjhfu47
    (r'^([a-z][-a-z0-9]*)-[a-f0-9]{6,}$', 'name-hash', 'Dynamic hash suffix (e.g., button-7234523bf)'),
    (r'^([a-z][-a-z0-9]*)_[a-f0-9]{6,}$', 'name_hash', 'Dynamic hash suffix with underscore'),
    (r'^([a-z][-a-z0-9]*)__[a-zA-Z0-9]{5,}$', 'name__hash', 'CSS Modules pattern (e.g., nav_bar__2RnO8)'),
    # Pure hash classes
    (r'^[a-f0-9]{6,12}$', 'pure-hash', 'Pure hash class - no stable part'),
    (r'^_[a-zA-Z0-9]{6,}$', '_hash', 'Underscore-prefixed hash'),
    # CSS-in-JS patterns
    (r'^sc-[a-zA-Z]{5,}$', 'styled-components', 'Styled Components hash'),
    (r'^css-[a-z0-9]{4,}$', 'emotion', 'Emotion CSS hash'),
    (r'^emotion-[a-z0-9]+$', 'emotion-*', 'Emotion hash'),
    (r'^makeStyles-[a-zA-Z]+-\d+$', 'mui-makeStyles', 'MUI makeStyles (dynamic)'),
    (r'^jss\d+$', 'jss', 'JSS generated class'),
    # Minified classes
    (r'^[a-zA-Z]{1,2}[0-9]{4,}$', 'minified', 'Minified class name'),
]

DYNAMIC_CLASS_PATTERNS = [
    (re.compile(pattern, re.IGNORECASE), label, reason)
    for pattern, label, reason in _DYNAMIC_CLASS_PATTERNS_RAW
]

# Software detection – all checks bundled into a single JS evaluation.
SOFTWARE_SIGNATURES = {
    'frontend_frameworks': [
        ('window.__NEXT_DATA__', 'Next.js'),
        ('window.__NUXT__', 'Nuxt.js'),
        ('window.angular', 'AngularJS'),
        ('window.ng', 'Angular'),
        ('window.__GATSBY', 'Gatsby'),
        ('window.Ember', 'Ember.js'),
        ('window.Vue', 'Vue.js'),
        ('document.querySelector("[data-reactroot]")', 'React'),
        ('document.querySelector("#__next")', 'Next.js'),
    ],
    'css_frameworks': [
        ('document.querySelector(".chakra-")', 'Chakra UI'),
        ('document.querySelector(".mantine-")', 'Mantine'),
        ('document.querySelector(".ant-")', 'Ant Design'),
        ('document.querySelector(".MuiBox-root")', 'Material UI'),
        ('document.querySelector(".bp4-")', 'Blueprint'),
    ],
    'analytics': [
        ('window.pendo', 'Pendo (already installed)'),
        ('window.analytics', 'Segment'),
        ('window.mixpanel', 'Mixpanel'),
        ('window.amplitude', 'Amplitude'),
        ('window.heap', 'Heap'),
        ('window.FS', 'FullStory'),
        ('window.Hotjar', 'Hotjar'),
        ('window.gtag', 'Google Tag Manager'),
        ('window.Intercom', 'Intercom'),
        ('window.Appcues', 'Appcues'),
        ('window.WalkMe', 'WalkMe'),
        ('window.Userpilot', 'Userpilot'),
        ('window.Chameleon', 'Chameleon'),
    ],
    'other': [
        ('window.Sentry', 'Sentry'),
        ('window.DD_RUM', 'Datadog RUM'),
        ('window.LaunchDarkly', 'LaunchDarkly'),
        ('window.Stripe', 'Stripe'),
    ],
}

# File extensions to skip during link extraction.
_SKIP_EXTENSIONS = frozenset(['.pdf', '.jpg', '.jpeg', '.png', '.gif', '.css', '.js', '.svg', '.ico', '.woff', '.woff2', '.ttf', '.eot', '.mp4', '.webm'])


# ---------------------------------------------------------------------------
# Pattern checkers (use pre-compiled regexes)
# ---------------------------------------------------------------------------

def check_dynamic_id(element_id: str) -> tuple[bool, str, str, bool]:
    """Check if an ID looks dynamic / framework-generated.

    Returns (is_dynamic, label, reason, has_stable_prefix).
    """
    if not element_id:
        return False, '', '', False

    for compiled, label, reason, has_prefix in DYNAMIC_ID_PATTERNS:
        if compiled.search(element_id):
            return True, label, reason, has_prefix

    return False, '', '', False


def check_dynamic_class(class_name: str) -> tuple[bool, str, str, str]:
    """Check if a CSS class looks dynamic.

    Returns (is_dynamic, label, reason, stable_prefix).
    Uses re.match (anchored) consistently – patterns already use ^ anchors.
    """
    if not class_name:
        return False, '', '', ''

    for compiled, label, reason in DYNAMIC_CLASS_PATTERNS:
        match = compiled.match(class_name)
        if match:
            stable_prefix = match.group(1) if match.lastindex and match.lastindex >= 1 else ''
            return True, label, reason, stable_prefix

    return False, '', '', ''


# ---------------------------------------------------------------------------
# Batched JS for element analysis (single browser round-trip)
# ---------------------------------------------------------------------------

_ANALYSE_ELEMENTS_JS = '''
(selector) => {
    const results = [];
    const elements = document.querySelectorAll(selector);
    for (const el of elements) {
        const pendoAttrs = [];
        let hasDataAttr = false;
        for (const attr of el.attributes) {
            if (attr.name.startsWith('data-pendo')) {
                pendoAttrs.push(attr.name + '="' + attr.value + '"');
            } else if (attr.name.startsWith('data-')) {
                hasDataAttr = true;
            }
        }
        const text = (el.textContent || '').trim().substring(0, 50);
        results.push({
            id: el.id || null,
            classes: el.className || '',
            pendoAttrs,
            hasDataAttr,
            text: text.length > 2 ? text : ''
        });
    }
    return results;
}
'''


def analyse_element(page: Page, selector: str, analysis: ElementAnalysis) -> None:
    """Analyse elements for Pendo tagging feasibility.

    Uses a single page.evaluate() call to extract all element data,
    then processes the results in Python – avoids N+1 browser round-trips.
    """
    try:
        elements_data = page.evaluate(_ANALYSE_ELEMENTS_JS, selector)
    except Exception as exc:
        log.debug('Failed to analyse elements for selector %s: %s', selector, exc)
        return

    for data in elements_data:
        analysis.total += 1

        # Pendo attributes
        pendo_attrs = data.get('pendoAttrs', [])
        if pendo_attrs:
            analysis.has_pendo_attr += 1
            if len(analysis.pendo_attr_examples) < 3:
                analysis.pendo_attr_examples.extend(pendo_attrs[:2])

        # Other data-* attributes
        if data.get('hasDataAttr'):
            analysis.has_data_attr += 1

        # ID stability check
        element_id = data.get('id')
        if element_id:
            is_dynamic, label, reason, has_prefix = check_dynamic_id(element_id)
            if is_dynamic:
                analysis.dynamic_ids += 1
                if len(analysis.dynamic_id_examples) < 5:
                    prefix_note = ' [has stable prefix]' if has_prefix else ''
                    analysis.dynamic_id_examples.append((element_id, reason + prefix_note))
            else:
                analysis.stable_ids += 1
                if len(analysis.stable_id_examples) < 5:
                    analysis.stable_id_examples.append(element_id)
        else:
            analysis.no_ids += 1

        # Class stability check
        classes = data.get('classes', '')
        if isinstance(classes, str):
            for class_name in classes.split():
                is_dynamic, label, reason, stable_prefix = check_dynamic_class(class_name)
                if is_dynamic and len(analysis.dynamic_class_examples) < 8:
                    prefix_note = f' [prefix: {stable_prefix}]' if stable_prefix else ' [NO stable prefix]'
                    analysis.dynamic_class_examples.append((class_name, reason + prefix_note))

        # Text content (useful for :contains selector)
        if data.get('text'):
            analysis.has_text_content += 1


# ---------------------------------------------------------------------------
# Batched dynamic class analysis
# ---------------------------------------------------------------------------

_ALL_CLASSES_JS = '''
() => {
    const classes = new Set();
    document.querySelectorAll('*').forEach(el => {
        el.classList.forEach(c => classes.add(c));
    });
    return Array.from(classes);
}
'''


def analyse_dynamic_classes(page: Page) -> tuple[int, list]:
    """Count and collect dynamic class examples across all elements."""
    dynamic_count = 0
    examples = []

    try:
        all_classes = page.evaluate(_ALL_CLASSES_JS)
    except Exception as exc:
        log.debug('Failed to collect classes: %s', exc)
        return dynamic_count, examples

    for class_name in all_classes:
        is_dynamic, label, reason, stable_prefix = check_dynamic_class(class_name)
        if is_dynamic:
            dynamic_count += 1
            if len(examples) < 15:
                prefix_note = f' [prefix: {stable_prefix}]' if stable_prefix else ' [NO stable prefix]'
                examples.append((class_name, reason + prefix_note))

    return dynamic_count, examples


# ---------------------------------------------------------------------------
# Batched software detection (single browser round-trip)
# ---------------------------------------------------------------------------

def _build_software_detection_js() -> tuple[str, dict]:
    """Build a single JS function that checks all software signatures at once.

    Returns (js_function_string, mapping) where mapping is
    {str(index): (category, name)}.  Keys are strings because JavaScript
    object keys are always strings when returned via Playwright.
    """
    checks = []
    index = 0
    mapping: dict[str, tuple[str, str]] = {}

    for category, signatures in SOFTWARE_SIGNATURES.items():
        for js_check, name in signatures:
            checks.append(f'try {{ r["{index}"] = !!{js_check}; }} catch(e) {{ r["{index}"] = false; }}')
            mapping[str(index)] = (category, name)
            index += 1

    js_body = '\n'.join(checks)
    js_fn = f'''
() => {{
    const r = {{}};
    {js_body}
    let gen = '';
    try {{ gen = document.querySelector("meta[name=generator]")?.content || ''; }} catch(e) {{}}
    r['gen'] = gen;
    return r;
}}
'''
    return js_fn, mapping


_SOFTWARE_JS, _SOFTWARE_MAPPING = _build_software_detection_js()


def detect_software(page: Page) -> SoftwareDetection:
    """Detect software and frameworks with a single page.evaluate() call."""
    detection = SoftwareDetection()

    try:
        results = page.evaluate(_SOFTWARE_JS)
    except Exception as exc:
        log.debug('Software detection failed: %s', exc)
        return detection

    detection.meta_generator = results.get('gen', '')

    category_sets = {
        'frontend_frameworks': set(),
        'css_frameworks': set(),
        'analytics': set(),
        'other': set(),
    }

    for key, (category, name) in _SOFTWARE_MAPPING.items():
        if results.get(key, False):
            category_sets.setdefault(category, set()).add(name)

    detection.frontend_frameworks = list(category_sets.get('frontend_frameworks', set()))
    detection.css_frameworks = list(category_sets.get('css_frameworks', set()))
    detection.analytics_tools = list(category_sets.get('analytics', set()))
    detection.other_tools = list(category_sets.get('other', set()))

    return detection


# ---------------------------------------------------------------------------
# Iframe, Shadow DOM, Canvas analysis
# ---------------------------------------------------------------------------

_IFRAME_JS = '''
() => {
    const iframes = [];
    document.querySelectorAll('iframe').forEach(iframe => {
        iframes.push({
            src: iframe.src || iframe.getAttribute('src') || '(no src)',
            id: iframe.id || null,
            name: iframe.name || null,
            title: iframe.title || null
        });
    });
    return iframes;
}
'''


def analyse_iframes(page: Page, page_url: str) -> list[IframeInfo]:
    """Find and analyse iframe elements."""
    iframes = []
    page_domain = urlparse(page_url).netloc

    try:
        iframe_data = page.evaluate(_IFRAME_JS)
    except Exception as exc:
        log.debug('Iframe analysis failed on %s: %s', page_url, exc)
        return iframes

    for data in iframe_data:
        src = data['src']
        iframe_domain = urlparse(src).netloc if src.startswith('http') else page_domain
        is_cross_origin = iframe_domain != page_domain and src != '(no src)'

        iframes.append(IframeInfo(
            src=src,
            page_url=page_url,
            is_cross_origin=is_cross_origin,
        ))

    return iframes


_SHADOW_DOM_JS = '''
() => {
    const elements = [];
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT);
    while (walker.nextNode()) {
        if (walker.currentNode.shadowRoot) {
            const el = walker.currentNode;
            elements.push({
                tag: el.tagName.toLowerCase(),
                id: el.id || null,
                classes: el.className || null
            });
        }
    }
    return elements;
}
'''


def detect_shadow_dom(page: Page, page_url: str) -> Optional[ShadowDOMInfo]:
    """Detect Shadow DOM with element details."""
    try:
        shadow_data = page.evaluate(_SHADOW_DOM_JS)
    except Exception as exc:
        log.debug('Shadow DOM detection failed on %s: %s', page_url, exc)
        return None

    if not shadow_data:
        return None

    element_tags = []
    for el in shadow_data[:5]:
        desc = el['tag']
        if el['id']:
            desc += f'#{el["id"]}'
        elif el['classes']:
            first_class = el['classes'].split()[0] if el['classes'] else ''
            if first_class:
                desc += f'.{first_class}'
        element_tags.append(desc)

    return ShadowDOMInfo(
        count=len(shadow_data),
        page_url=page_url,
        element_tags=element_tags,
    )


_CANVAS_JS = '''
() => {
    const canvases = [];
    document.querySelectorAll('canvas').forEach(canvas => {
        const rect = canvas.getBoundingClientRect();
        canvases.push({
            id: canvas.id || null,
            width: canvas.width || rect.width,
            height: canvas.height || rect.height,
            classes: canvas.className || null
        });
    });
    return canvases;
}
'''


def analyse_canvas(page: Page, page_url: str) -> Optional[CanvasInfo]:
    """Detect canvas elements with details."""
    try:
        canvas_data = page.evaluate(_CANVAS_JS)
    except Exception as exc:
        log.debug('Canvas analysis failed on %s: %s', page_url, exc)
        return None

    if not canvas_data:
        return None

    dimensions = []
    for c in canvas_data[:5]:
        desc = f'{int(c["width"])}x{int(c["height"])}'
        if c['id']:
            desc += f' (id={c["id"]})'
        elif c['classes']:
            first_class = c['classes'].split()[0] if c['classes'] else ''
            if first_class:
                desc += f' (.{first_class})'
        dimensions.append(desc)

    return CanvasInfo(
        count=len(canvas_data),
        page_url=page_url,
        dimensions=dimensions,
    )


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Page interaction helpers
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
        except Exception:
            pass  # Popup dismissal is best-effort


# ---------------------------------------------------------------------------
# Page analysis orchestrator
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# URL display helper
# ---------------------------------------------------------------------------

def get_short_url(url: str, max_len: int = 50) -> str:
    """Shorten URL for display."""
    parsed = urlparse(url)
    path = parsed.path
    if len(path) > max_len:
        path = '...' + path[-(max_len - 3):]
    return path if path else '/'


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def generate_report(url: str, analyses: list[PageAnalysis], software: SoftwareDetection) -> str:
    """Generate the human-readable feasibility report."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')

    # Aggregate data
    total_buttons = sum(a.buttons.total for a in analyses)
    total_inputs = sum(a.inputs.total for a in analyses)

    stable_button_ids = sum(a.buttons.stable_ids for a in analyses)
    stable_input_ids = sum(a.inputs.stable_ids for a in analyses)

    dynamic_button_ids = sum(a.buttons.dynamic_ids for a in analyses)
    dynamic_input_ids = sum(a.inputs.dynamic_ids for a in analyses)

    no_id_buttons = sum(a.buttons.no_ids for a in analyses)
    no_id_inputs = sum(a.inputs.no_ids for a in analyses)

    pendo_attr_buttons = sum(a.buttons.has_pendo_attr for a in analyses)
    pendo_attr_inputs = sum(a.inputs.has_pendo_attr for a in analyses)

    data_attr_buttons = sum(a.buttons.has_data_attr for a in analyses)

    text_content_buttons = sum(a.buttons.has_text_content for a in analyses)

    total_dynamic_classes = sum(a.dynamic_class_count for a in analyses)

    # Collect examples
    all_dynamic_id_examples = []
    all_stable_id_examples = []
    all_pendo_attr_examples = []
    all_dynamic_class_examples = []

    for a in analyses:
        for ea in (a.buttons, a.inputs):
            all_dynamic_id_examples.extend(ea.dynamic_id_examples)
            all_stable_id_examples.extend(ea.stable_id_examples)
            all_pendo_attr_examples.extend(ea.pendo_attr_examples)
            all_dynamic_class_examples.extend(ea.dynamic_class_examples)
        all_dynamic_class_examples.extend(a.dynamic_class_examples)

    # Deduplicate dynamic classes
    seen_dynamic_classes: set[str] = set()
    unique_dynamic_class_examples = []
    for ex in all_dynamic_class_examples:
        if ex[0] not in seen_dynamic_classes:
            seen_dynamic_classes.add(ex[0])
            unique_dynamic_class_examples.append(ex)

    # Collect iframes, shadow DOM, canvas with locations
    all_iframes = []
    all_shadow_dom = []
    all_canvas = []

    for a in analyses:
        all_iframes.extend(a.iframes)
        if a.shadow_dom:
            all_shadow_dom.append(a.shadow_dom)
        if a.canvas:
            all_canvas.append(a.canvas)

    total_iframe_count = len(all_iframes)
    total_shadow_roots = sum(s.count for s in all_shadow_dom)
    total_canvas_count = sum(c.count for c in all_canvas)

    # Calculate scores
    button_id_score = (stable_button_ids / total_buttons * 100) if total_buttons > 0 else 100
    input_id_score = (stable_input_ids / total_inputs * 100) if total_inputs > 0 else 100

    weighted_stable = (stable_button_ids * 3) + (stable_input_ids * 2)
    weighted_total = (total_buttons * 3) + (total_inputs * 2)
    overall_id_score = (weighted_stable / weighted_total * 100) if weighted_total > 0 else 100

    # Risk level
    has_critical_dynamic_css = len(unique_dynamic_class_examples) > 0
    risk_points = 0

    if overall_id_score < 50:
        risk_points += 3
    elif overall_id_score < 70:
        risk_points += 2
    elif overall_id_score < 85:
        risk_points += 1

    if has_critical_dynamic_css and total_dynamic_classes > 20:
        risk_points += 2

    if total_shadow_roots > 0:
        risk_points += 2

    if total_iframe_count > 2:
        risk_points += 1

    risk_level = 'HIGH' if risk_points >= 4 else 'MODERATE' if risk_points >= 2 else 'LOW'

    # Build report
    lines = []
    lines.append('=' * 65)
    lines.append('              PENDO FEASIBILITY REPORT')
    lines.append('=' * 65)
    lines.append(f'Site: {url}')
    lines.append(f'Pages Analysed: {len(analyses)}')
    lines.append(f'Date: {timestamp}')
    lines.append(f'Risk Level: {risk_level}')
    lines.append('')

    # CRITICAL WARNING - Dynamic CSS
    if has_critical_dynamic_css:
        lines.append('!' * 65)
        lines.append('!!! CRITICAL: DYNAMIC CSS SELECTORS DETECTED !!!')
        lines.append('!' * 65)
        lines.append('')
        lines.append('The following dynamic class patterns were found.')
        lines.append('These change on rebuild/deploy and will BREAK Pendo tags.')
        lines.append('')

        for class_name, reason in unique_dynamic_class_examples[:10]:
            lines.append(f'  "{class_name}"')
            lines.append(f'     -> {reason}')
            lines.append('')

        if len(unique_dynamic_class_examples) > 10:
            lines.append(f'  ... and {len(unique_dynamic_class_examples) - 10} more dynamic classes')
            lines.append('')

        lines.append('WORKAROUNDS (per Pendo docs):')
        lines.append('  1. Use starts-with [class^="prefix-"] if stable prefix exists')
        lines.append('  2. Use :contains("Button Text") for elements with text')
        lines.append('  3. Request engineering add data-pendo-* attributes')
        lines.append('  4. Use stable IDs instead of classes')
        lines.append('')
        lines.append('!' * 65)
        lines.append('')

    # Section 0: Detected Software
    lines.append('-' * 65)
    lines.append('0. DETECTED SOFTWARE')
    lines.append('-' * 65)

    if software.frontend_frameworks:
        lines.append(f"Frontend: {', '.join(software.frontend_frameworks)}")
    if software.css_frameworks:
        lines.append(f"UI Framework: {', '.join(software.css_frameworks)}")
    if software.analytics_tools:
        pendo_note = ' [ALREADY INSTALLED]' if 'Pendo (already installed)' in software.analytics_tools else ''
        competitors = [t for t in software.analytics_tools if t in ['Appcues', 'WalkMe', 'Userpilot', 'Chameleon']]
        competitor_note = f' [COMPETITORS: {", ".join(competitors)}]' if competitors else ''
        lines.append(f"Analytics: {', '.join(software.analytics_tools)}{pendo_note}{competitor_note}")
    if software.other_tools:
        lines.append(f"Other: {', '.join(software.other_tools)}")

    if not any([software.frontend_frameworks, software.css_frameworks, software.analytics_tools]):
        lines.append('No common frameworks detected')

    lines.append('')

    # Section 1: ID Analysis
    lines.append('-' * 65)
    lines.append('1. ELEMENT ID ANALYSIS (Primary for Pendo)')
    lines.append('-' * 65)
    lines.append('')
    lines.append(f'Overall ID Stability Score: {overall_id_score:.0f}%')
    lines.append('')

    lines.append('BUTTONS (highest priority for tagging):')
    lines.append(f'  Total: {total_buttons}')
    lines.append(f'  With stable IDs: {stable_button_ids} ({button_id_score:.0f}%) {"[GOOD]" if button_id_score >= 70 else "[NEEDS WORK]"}')
    lines.append(f'  With dynamic IDs: {dynamic_button_ids} {"[WARNING]" if dynamic_button_ids > 0 else ""}')
    lines.append(f'  Without IDs: {no_id_buttons}')
    lines.append(f'  With data-pendo-* attr: {pendo_attr_buttons} {"[EXCELLENT]" if pendo_attr_buttons > 0 else ""}')
    lines.append(f'  With other data-* attr: {data_attr_buttons}')
    lines.append(f'  With text content: {text_content_buttons} (can use :contains)')
    lines.append('')

    lines.append('INPUTS:')
    lines.append(f'  Total: {total_inputs}')
    lines.append(f'  With stable IDs: {stable_input_ids} ({input_id_score:.0f}%) {"[GOOD]" if input_id_score >= 70 else "[NEEDS WORK]"}')
    lines.append(f'  With dynamic IDs: {dynamic_input_ids} {"[WARNING]" if dynamic_input_ids > 0 else ""}')
    lines.append(f'  Without IDs: {no_id_inputs}')
    lines.append(f'  With data-pendo-* attr: {pendo_attr_inputs} {"[EXCELLENT]" if pendo_attr_inputs > 0 else ""}')
    lines.append('')

    if all_stable_id_examples:
        lines.append('Example STABLE IDs (good for targeting):')
        for ex in list(set(all_stable_id_examples))[:5]:
            lines.append(f'  id="{ex}"')
        lines.append('')

    if all_dynamic_id_examples:
        lines.append('Example DYNAMIC IDs (problematic):')
        for ex_id, reason in all_dynamic_id_examples[:5]:
            lines.append(f'  id="{ex_id}"')
            lines.append(f'     -> {reason}')
        lines.append('')

    if all_pendo_attr_examples:
        lines.append('Example data-pendo-* attributes found (excellent):')
        for attr in list(set(all_pendo_attr_examples))[:3]:
            lines.append(f'  {attr}')
        lines.append('')

    # Section 2: Dynamic CSS Detail
    lines.append('-' * 65)
    lines.append('2. CSS CLASS ANALYSIS')
    lines.append('-' * 65)
    lines.append(f'Total dynamic classes detected: {total_dynamic_classes}')
    lines.append('')

    if total_dynamic_classes == 0:
        lines.append('[GOOD] No dynamic CSS class patterns detected.')
        lines.append('CSS selectors should be stable for Pendo tagging.')
    else:
        lines.append('[WARNING] Dynamic CSS classes found.')
        lines.append('Avoid using these directly in Pendo feature rules.')
        lines.append('')
        lines.append('Pendo workarounds:')
        lines.append('  - [class^="stable-prefix-"] matches class starting with prefix')
        lines.append('  - [class$="-suffix"] matches class ending with suffix')
        lines.append('  - [class*="contains"] matches class containing text')
        lines.append('  - :contains("Button Text") matches element text')

    lines.append('')

    # Section 3: Iframes (with locations)
    lines.append('-' * 65)
    lines.append('3. IFRAMES')
    lines.append('-' * 65)
    lines.append(f'Total Count: {total_iframe_count} {"[OK]" if total_iframe_count == 0 else "[WARNING]"}')

    if total_iframe_count > 0:
        lines.append('')
        lines.append('Pendo loses visitor context across iframe boundaries.')
        lines.append('Guides/analytics will not work inside cross-origin iframes.')
        lines.append('')
        lines.append('IFRAME LOCATIONS:')

        iframe_by_page: dict[str, list] = {}
        for iframe in all_iframes:
            page_path = get_short_url(iframe.page_url)
            iframe_by_page.setdefault(page_path, []).append(iframe)

        for page_path, iframes_list in iframe_by_page.items():
            lines.append(f'  Page: {page_path}')
            for iframe in iframes_list[:3]:
                origin = '[CROSS-ORIGIN]' if iframe.is_cross_origin else '[same-origin]'
                src_display = iframe.src[:50] + '...' if len(iframe.src) > 50 else iframe.src
                lines.append(f'    {origin} {src_display}')
            if len(iframes_list) > 3:
                lines.append(f'    ... and {len(iframes_list) - 3} more on this page')
            lines.append('')

    lines.append('')

    # Section 4: Shadow DOM (with locations)
    lines.append('-' * 65)
    lines.append('4. SHADOW DOM')
    lines.append('-' * 65)
    lines.append(f'Total Shadow Roots: {total_shadow_roots} {"[OK]" if total_shadow_roots == 0 else "[WARNING]"}')

    if total_shadow_roots > 0:
        lines.append('')
        lines.append('Pendo cannot pierce Shadow DOM boundaries.')
        lines.append('Elements inside shadow roots are invisible to Pendo selectors.')
        lines.append('')
        lines.append('SHADOW DOM LOCATIONS:')

        for shadow in all_shadow_dom:
            page_path = get_short_url(shadow.page_url)
            lines.append(f'  Page: {page_path}')
            lines.append(f'    Count: {shadow.count} shadow root(s)')
            if shadow.element_tags:
                lines.append(f'    Elements: {", ".join(shadow.element_tags)}')
            lines.append('')

        lines.append('Workaround: Use Track Events API or request engineering expose')
        lines.append('            data attributes outside the shadow boundary.')

    lines.append('')

    # Section 5: Canvas (with locations)
    lines.append('-' * 65)
    lines.append('5. CANVAS ELEMENTS')
    lines.append('-' * 65)
    lines.append(f'Total Count: {total_canvas_count} {"[OK]" if total_canvas_count == 0 else "[INFO]"}')

    if total_canvas_count > 0:
        lines.append('')
        lines.append('Canvas renders as pixels; clicks inside are not taggable.')
        lines.append('Common uses: Charts, graphs, image editors, maps, games.')
        lines.append('')
        lines.append('CANVAS LOCATIONS:')

        for canvas in all_canvas:
            page_path = get_short_url(canvas.page_url)
            lines.append(f'  Page: {page_path}')
            lines.append(f'    Count: {canvas.count} canvas element(s)')
            if canvas.dimensions:
                lines.append(f'    Sizes: {", ".join(canvas.dimensions)}')
            lines.append('')

        lines.append('Workaround: Use Track Events API if canvas interactions need tracking.')

    lines.append('')

    # Summary
    lines.append('=' * 65)
    lines.append('              SUMMARY & RECOMMENDATIONS')
    lines.append('=' * 65)
    lines.append(f'Overall Risk: {risk_level}')
    lines.append('')

    lines.append('TAGGING STRATEGY:')

    if overall_id_score >= 80 and not has_critical_dynamic_css:
        lines.append('  [GOOD] Standard Pendo tagging should work well.')
        lines.append('  Use IDs as primary selectors where available.')
    elif overall_id_score >= 50:
        lines.append('  [MODERATE] Mixed approach needed.')
        lines.append('  - Use stable IDs where available')
        lines.append('  - Use :contains("text") for buttons with clear labels')
        lines.append('  - Use [class^="prefix-"] for classes with stable prefixes')
        lines.append('  - Request data-pendo-* attrs for critical CTAs')
    else:
        lines.append('  [CHALLENGING] Significant work required.')
        lines.append('  - Request engineering add data-pendo-* attributes')
        lines.append('  - Use :contains() extensively')
        lines.append('  - Avoid CSS class selectors')
        lines.append('  - Consider Track Events API for complex elements')

    lines.append('')

    concerns = []
    if button_id_score < 70:
        concerns.append(f'Low button ID stability ({button_id_score:.0f}%)')
    if has_critical_dynamic_css:
        concerns.append(f'Dynamic CSS classes detected ({total_dynamic_classes} found)')
    if total_shadow_roots > 0:
        pages_with_shadow = [get_short_url(s.page_url) for s in all_shadow_dom]
        concerns.append(f'Shadow DOM on: {", ".join(pages_with_shadow[:3])}')
    if total_iframe_count > 2:
        concerns.append(f'Multiple iframes ({total_iframe_count})')

    if concerns:
        lines.append('KEY CONCERNS:')
        for c in concerns:
            lines.append(f'  * {c}')
        lines.append('')

    positives = []
    if pendo_attr_buttons > 0 or pendo_attr_inputs > 0:
        positives.append(f'data-pendo-* attributes already in use ({pendo_attr_buttons + pendo_attr_inputs} elements)')
    if stable_button_ids > 0:
        positives.append(f'{stable_button_ids} buttons have stable IDs')
    if text_content_buttons > 0:
        positives.append(f'{text_content_buttons} buttons have text (can use :contains)')

    if positives:
        lines.append('POSITIVE INDICATORS:')
        for p in positives:
            lines.append(f'  + {p}')
        lines.append('')

    lines.append('RECOMMENDED NEXT STEPS:')
    if overall_id_score < 80 or has_critical_dynamic_css:
        lines.append('  1. Share this report with customer engineering team')
        lines.append('  2. Request data-pendo-* attributes on key CTAs')
        lines.append('  3. Identify elements that can use :contains() workaround')
        lines.append('  4. Plan for Track Events API where needed')
    else:
        lines.append('  1. Proceed with standard Pendo implementation')
        lines.append('  2. Prioritise ID-based selectors')
        lines.append('  3. Test feature tags after deployment')

    lines.append('')
    lines.append('=' * 65)

    lines.append('')
    lines.append('Pages Scanned:')
    for i, a in enumerate(analyses, 1):
        short = a.url[:60] + '...' if len(a.url) > 60 else a.url
        lines.append(f'  {i}. {short}')

    return '\n'.join(lines)


def generate_json_report(url: str, analyses: list[PageAnalysis], software: SoftwareDetection) -> dict:
    """Generate a JSON report for programmatic use."""
    domain = urlparse(url).netloc
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
    pages = []
    for a in analyses:
        pages.append({
            'url': a.url,
            'buttons': a.buttons.__dict__,
            'inputs': a.inputs.__dict__,
            'links': a.links.__dict__,
            'dynamic_class_count': a.dynamic_class_count,
            'dynamic_class_examples': a.dynamic_class_examples,
            'iframes': [i.__dict__ for i in a.iframes],
            'shadow_dom': a.shadow_dom.__dict__ if a.shadow_dom else None,
            'canvas': a.canvas.__dict__ if a.canvas else None,
        })
    report = {
        'meta': {
            'site': url,
            'domain': domain,
            'pages_analysed': len(analyses),
            'timestamp': timestamp,
        },
        'software': software.__dict__,
        'pages': pages,
    }
    return report


# ---------------------------------------------------------------------------
# Login handling
# ---------------------------------------------------------------------------

def apply_login(page: Page, config: ScrapeConfig, login_event=None) -> None:
    """Handle login based on config.

    Args:
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


# ---------------------------------------------------------------------------
# Scan orchestrator
# ---------------------------------------------------------------------------

def run_scan(
    start_url: str,
    config: ScrapeConfig,
    progress_callback=None,
    login_event=None,
) -> ScanResult:
    """Run a full scan and return structured results.

    Args:
        progress_callback: Optional callable(str). Called with human-readable
            progress messages so a UI can display live status.
        login_event: Optional threading.Event. Passed to apply_login so the
            UI can signal "continue" instead of blocking on stdin.
    """
    _progress = progress_callback or (lambda msg: None)

    if not start_url.startswith('http'):
        start_url = 'https://' + start_url

    with sync_playwright() as p:
        _progress(f'LAUNCHING BROWSER...')
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
