"""Element analysis, selector suggestion, software detection, and special-element analysis.

Contains all functions that evaluate pages via Playwright's page.evaluate()
and process the resulting data in Python.
"""

import logging
import re
from typing import Optional
from urllib.parse import urlparse

from playwright.sync_api import Page

from .models import (
    SelectorSuggestion,
    ElementAnalysis,
    IframeInfo,
    ShadowDOMInfo,
    CanvasInfo,
    SoftwareDetection,
)
from .patterns import (
    check_dynamic_id,
    check_dynamic_class,
    SOFTWARE_SIGNATURES,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Batched JS for element analysis (single browser round-trip)
# ---------------------------------------------------------------------------

_ANALYSE_ELEMENTS_JS = '''
(selector) => {
    const results = [];
    const elements = document.querySelectorAll(selector);
    for (const el of elements) {
        const pendoAttrs = [];
        const dataAttrs = {};
        for (const attr of el.attributes) {
            if (attr.name.startsWith('data-pendo')) {
                pendoAttrs.push(attr.name + '="' + attr.value + '"');
            } else if (attr.name.startsWith('data-')) {
                dataAttrs[attr.name] = attr.value;
            }
        }
        const text = (el.textContent || '').trim().substring(0, 50);
        results.push({
            id: el.id || null,
            tag: el.tagName.toLowerCase(),
            classes: el.className || '',
            pendoAttrs,
            dataAttrs,
            ariaLabel: el.getAttribute('aria-label') || '',
            role: el.getAttribute('role') || '',
            type: el.getAttribute('type') || '',
            name: el.getAttribute('name') || '',
            placeholder: el.getAttribute('placeholder') || '',
            title: el.getAttribute('title') || '',
            text: text.length > 2 ? text : ''
        });
    }
    return results;
}
'''


# Preferred data-* attribute names for selectors (ordered by reliability).
_PREFERRED_DATA_ATTRS = [
    'data-testid', 'data-test-id', 'data-test',
    'data-qa', 'data-cy', 'data-e2e',
    'data-id', 'data-name', 'data-action',
]


def suggest_selector(data: dict) -> Optional[SelectorSuggestion]:
    """Generate the best Pendo-compatible selector for a single element.

    Returns None if no reasonable selector can be constructed.

    Priority order:
      1. [data-testid="..."] or similar test attributes  -> excellent
      2. [aria-label="..."]                               -> good
      3. :contains("text") for short, clear button text   -> good
      4. [class^="stable-prefix-"] for dynamic classes     -> acceptable
      5. tag[name="..."] or tag[type="..."][placeholder]  -> acceptable
    """
    tag = data.get('tag', '')
    text = data.get('text', '')
    aria_label = data.get('ariaLabel', '')
    data_attrs = data.get('dataAttrs', {})
    name_attr = data.get('name', '')
    type_attr = data.get('type', '')
    placeholder = data.get('placeholder', '')
    title_attr = data.get('title', '')
    classes = data.get('classes', '')

    # Build a human-readable description of the element.
    if text:
        desc = f'{tag.capitalize()} "{text[:30]}"'
    elif aria_label:
        desc = f'{tag.capitalize()} [aria-label="{aria_label[:30]}"]'
    elif name_attr:
        desc = f'{tag.capitalize()} [name="{name_attr}"]'
    else:
        desc = f'{tag.capitalize()} element'

    # --- Priority 1: Preferred data-* test attributes ---
    for attr_name in _PREFERRED_DATA_ATTRS:
        val = data_attrs.get(attr_name, '')
        if val:
            selector = f'{tag}[{attr_name}="{val}"]'
            return SelectorSuggestion(desc, selector, 'data-attr', 'excellent')

    # Any other non-dynamic data-* attribute with a short, stable-looking value.
    for attr_name, val in data_attrs.items():
        if val and len(val) < 60 and not re.search(r'[a-f0-9]{8,}', val):
            selector = f'{tag}[{attr_name}="{val}"]'
            return SelectorSuggestion(desc, selector, 'data-attr', 'good')

    # --- Priority 2: aria-label ---
    if aria_label and len(aria_label) < 60:
        selector = f'{tag}[aria-label="{aria_label}"]'
        return SelectorSuggestion(desc, selector, 'aria-label', 'good')

    # --- Priority 3: :contains("text") for buttons/links with clear text ---
    if text and len(text) <= 40 and tag in ('button', 'a'):
        selector = f'{tag}:contains("{text}")'
        return SelectorSuggestion(desc, selector, 'contains', 'good')

    # --- Priority 4: title attribute ---
    if title_attr and len(title_attr) < 60:
        selector = f'{tag}[title="{title_attr}"]'
        return SelectorSuggestion(desc, selector, 'attribute', 'acceptable')

    # --- Priority 5: Class with stable prefix ---
    if isinstance(classes, str):
        for class_name in classes.split():
            is_dynamic, _label, _reason, stable_prefix = check_dynamic_class(class_name)
            if is_dynamic and stable_prefix:
                selector = f'{tag}[class^="{stable_prefix}"]'
                return SelectorSuggestion(desc, selector, 'class-prefix', 'acceptable')

    # --- Priority 6: name/type/placeholder for form elements ---
    if name_attr and tag in ('input', 'select', 'textarea'):
        selector = f'{tag}[name="{name_attr}"]'
        return SelectorSuggestion(desc, selector, 'attribute', 'acceptable')

    if type_attr and placeholder and tag == 'input':
        selector = f'input[type="{type_attr}"][placeholder="{placeholder}"]'
        return SelectorSuggestion(desc, selector, 'attribute', 'acceptable')

    if placeholder and tag == 'input':
        selector = f'input[placeholder="{placeholder}"]'
        return SelectorSuggestion(desc, selector, 'attribute', 'acceptable')

    return None


# ---------------------------------------------------------------------------
# Element analysis
# ---------------------------------------------------------------------------

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
        if data.get('dataAttrs'):
            analysis.has_data_attr += 1

        # ID stability check
        element_id = data.get('id')
        needs_suggestion = False
        if element_id:
            is_dynamic, label, reason, has_prefix = check_dynamic_id(element_id)
            if is_dynamic:
                analysis.dynamic_ids += 1
                needs_suggestion = True
                if len(analysis.dynamic_id_examples) < 5:
                    prefix_note = ' [has stable prefix]' if has_prefix else ''
                    analysis.dynamic_id_examples.append((element_id, reason + prefix_note))
            else:
                analysis.stable_ids += 1
                if len(analysis.stable_id_examples) < 5:
                    analysis.stable_id_examples.append(element_id)
        else:
            analysis.no_ids += 1
            needs_suggestion = True

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

        # Generate selector suggestion for elements without a stable ID.
        # Skip if element already has data-pendo-* (already excellent).
        if needs_suggestion and not pendo_attrs and len(analysis.selector_suggestions) < 15:
            suggestion = suggest_selector(data)
            if suggestion:
                analysis.selector_suggestions.append(suggestion)


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
# Iframe analysis
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


# ---------------------------------------------------------------------------
# Shadow DOM detection
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Canvas analysis
# ---------------------------------------------------------------------------

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
