"""Report generation: human-readable text and JSON formats.

The text report is designed for copy-paste into customer-facing documents.
The JSON report is used for programmatic consumption and UI display.
"""

from datetime import datetime
from urllib.parse import urlparse

from .models import (
    SelectorSuggestion,
    ElementAnalysis,
    PageAnalysis,
    SoftwareDetection,
)


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
# Aggregation helpers (extracted from generate_report for readability)
# ---------------------------------------------------------------------------

def _aggregate_data(analyses: list[PageAnalysis]) -> dict:
    """Aggregate element counts and examples across all page analyses.

    Returns a dict of computed values used by both the text and summary
    sections of the report.
    """
    d: dict = {}

    d['total_buttons'] = sum(a.buttons.total for a in analyses)
    d['total_inputs'] = sum(a.inputs.total for a in analyses)

    d['stable_button_ids'] = sum(a.buttons.stable_ids for a in analyses)
    d['stable_input_ids'] = sum(a.inputs.stable_ids for a in analyses)

    d['dynamic_button_ids'] = sum(a.buttons.dynamic_ids for a in analyses)
    d['dynamic_input_ids'] = sum(a.inputs.dynamic_ids for a in analyses)

    d['no_id_buttons'] = sum(a.buttons.no_ids for a in analyses)
    d['no_id_inputs'] = sum(a.inputs.no_ids for a in analyses)

    d['pendo_attr_buttons'] = sum(a.buttons.has_pendo_attr for a in analyses)
    d['pendo_attr_inputs'] = sum(a.inputs.has_pendo_attr for a in analyses)

    d['data_attr_buttons'] = sum(a.buttons.has_data_attr for a in analyses)
    d['text_content_buttons'] = sum(a.buttons.has_text_content for a in analyses)
    d['total_dynamic_classes'] = sum(a.dynamic_class_count for a in analyses)

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

    d['all_dynamic_id_examples'] = all_dynamic_id_examples
    d['all_stable_id_examples'] = all_stable_id_examples
    d['all_pendo_attr_examples'] = all_pendo_attr_examples

    # Deduplicate dynamic classes
    seen: set[str] = set()
    unique = []
    for ex in all_dynamic_class_examples:
        if ex[0] not in seen:
            seen.add(ex[0])
            unique.append(ex)
    d['unique_dynamic_class_examples'] = unique

    # Collect special elements with locations
    all_iframes = []
    all_shadow_dom = []
    all_canvas = []
    for a in analyses:
        all_iframes.extend(a.iframes)
        if a.shadow_dom:
            all_shadow_dom.append(a.shadow_dom)
        if a.canvas:
            all_canvas.append(a.canvas)

    d['all_iframes'] = all_iframes
    d['all_shadow_dom'] = all_shadow_dom
    d['all_canvas'] = all_canvas
    d['total_iframe_count'] = len(all_iframes)
    d['total_shadow_roots'] = sum(s.count for s in all_shadow_dom)
    d['total_canvas_count'] = sum(c.count for c in all_canvas)

    return d


def _calculate_scores(d: dict) -> dict:
    """Calculate ID stability scores and risk level from aggregated data."""
    tb = d['total_buttons']
    ti = d['total_inputs']

    d['button_id_score'] = (d['stable_button_ids'] / tb * 100) if tb > 0 else 100
    d['input_id_score'] = (d['stable_input_ids'] / ti * 100) if ti > 0 else 100

    weighted_stable = (d['stable_button_ids'] * 3) + (d['stable_input_ids'] * 2)
    weighted_total = (tb * 3) + (ti * 2)
    d['overall_id_score'] = (weighted_stable / weighted_total * 100) if weighted_total > 0 else 100

    # Risk level
    d['has_critical_dynamic_css'] = len(d['unique_dynamic_class_examples']) > 0
    risk_points = 0

    if d['overall_id_score'] < 50:
        risk_points += 3
    elif d['overall_id_score'] < 70:
        risk_points += 2
    elif d['overall_id_score'] < 85:
        risk_points += 1

    if d['has_critical_dynamic_css'] and d['total_dynamic_classes'] > 20:
        risk_points += 2

    if d['total_shadow_roots'] > 0:
        risk_points += 2

    if d['total_iframe_count'] > 2:
        risk_points += 1

    d['risk_level'] = 'HIGH' if risk_points >= 4 else 'MODERATE' if risk_points >= 2 else 'LOW'
    return d


# ---------------------------------------------------------------------------
# Report section builders
# ---------------------------------------------------------------------------

def _section_header(d: dict, url: str, timestamp: str, num_pages: int) -> list[str]:
    """Build the report header lines."""
    return [
        '=' * 65,
        '              PENDO FEASIBILITY REPORT',
        '=' * 65,
        f'Site: {url}',
        f'Pages Analysed: {num_pages}',
        f'Date: {timestamp}',
        f'Risk Level: {d["risk_level"]}',
        '',
    ]


def _section_dynamic_css_warning(d: dict) -> list[str]:
    """Build the critical dynamic-CSS warning block (if applicable)."""
    if not d['has_critical_dynamic_css']:
        return []

    lines = [
        '!' * 65,
        '!!! CRITICAL: DYNAMIC CSS SELECTORS DETECTED !!!',
        '!' * 65,
        '',
        'The following dynamic class patterns were found.',
        'These change on rebuild/deploy and will BREAK Pendo tags.',
        '',
    ]

    for class_name, reason in d['unique_dynamic_class_examples'][:10]:
        lines.append(f'  "{class_name}"')
        lines.append(f'     -> {reason}')
        lines.append('')

    if len(d['unique_dynamic_class_examples']) > 10:
        lines.append(f'  ... and {len(d["unique_dynamic_class_examples"]) - 10} more dynamic classes')
        lines.append('')

    lines += [
        'WORKAROUNDS (per Pendo docs):',
        '  1. Use starts-with [class^="prefix-"] if stable prefix exists',
        '  2. Use :contains("Button Text") for elements with text',
        '  3. Request engineering add data-pendo-* attributes',
        '  4. Use stable IDs instead of classes',
        '',
        '!' * 65,
        '',
    ]
    return lines


def _section_software(software: SoftwareDetection) -> list[str]:
    """Build the detected-software section."""
    lines = [
        '-' * 65,
        '0. DETECTED SOFTWARE',
        '-' * 65,
    ]

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
    return lines


def _section_id_analysis(d: dict) -> list[str]:
    """Build the element-ID analysis section."""
    lines = [
        '-' * 65,
        '1. ELEMENT ID ANALYSIS (Primary for Pendo)',
        '-' * 65,
        '',
        f'Overall ID Stability Score: {d["overall_id_score"]:.0f}%',
        '',
    ]

    bs = d['button_id_score']
    lines += [
        'BUTTONS (highest priority for tagging):',
        f'  Total: {d["total_buttons"]}',
        f'  With stable IDs: {d["stable_button_ids"]} ({bs:.0f}%) {"[GOOD]" if bs >= 70 else "[NEEDS WORK]"}',
        f'  With dynamic IDs: {d["dynamic_button_ids"]} {"[WARNING]" if d["dynamic_button_ids"] > 0 else ""}',
        f'  Without IDs: {d["no_id_buttons"]}',
        f'  With data-pendo-* attr: {d["pendo_attr_buttons"]} {"[EXCELLENT]" if d["pendo_attr_buttons"] > 0 else ""}',
        f'  With other data-* attr: {d["data_attr_buttons"]}',
        f'  With text content: {d["text_content_buttons"]} (can use :contains)',
        '',
    ]

    iis = d['input_id_score']
    lines += [
        'INPUTS:',
        f'  Total: {d["total_inputs"]}',
        f'  With stable IDs: {d["stable_input_ids"]} ({iis:.0f}%) {"[GOOD]" if iis >= 70 else "[NEEDS WORK]"}',
        f'  With dynamic IDs: {d["dynamic_input_ids"]} {"[WARNING]" if d["dynamic_input_ids"] > 0 else ""}',
        f'  Without IDs: {d["no_id_inputs"]}',
        f'  With data-pendo-* attr: {d["pendo_attr_inputs"]} {"[EXCELLENT]" if d["pendo_attr_inputs"] > 0 else ""}',
        '',
    ]

    if d['all_stable_id_examples']:
        lines.append('Example STABLE IDs (good for targeting):')
        for ex in list(set(d['all_stable_id_examples']))[:5]:
            lines.append(f'  id="{ex}"')
        lines.append('')

    if d['all_dynamic_id_examples']:
        lines.append('Example DYNAMIC IDs (problematic):')
        for ex_id, reason in d['all_dynamic_id_examples'][:5]:
            lines.append(f'  id="{ex_id}"')
            lines.append(f'     -> {reason}')
        lines.append('')

    if d['all_pendo_attr_examples']:
        lines.append('Example data-pendo-* attributes found (excellent):')
        for attr in list(set(d['all_pendo_attr_examples']))[:3]:
            lines.append(f'  {attr}')
        lines.append('')

    return lines


def _section_css_classes(d: dict) -> list[str]:
    """Build the CSS class analysis section."""
    lines = [
        '-' * 65,
        '2. CSS CLASS ANALYSIS',
        '-' * 65,
        f'Total dynamic classes detected: {d["total_dynamic_classes"]}',
        '',
    ]

    if d['total_dynamic_classes'] == 0:
        lines += [
            '[GOOD] No dynamic CSS class patterns detected.',
            'CSS selectors should be stable for Pendo tagging.',
        ]
    else:
        lines += [
            '[WARNING] Dynamic CSS classes found.',
            'Avoid using these directly in Pendo feature rules.',
            '',
            'Pendo workarounds:',
            '  - [class^="stable-prefix-"] matches class starting with prefix',
            '  - [class$="-suffix"] matches class ending with suffix',
            '  - [class*="contains"] matches class containing text',
            '  - :contains("Button Text") matches element text',
        ]

    lines.append('')
    return lines


def _section_iframes(d: dict) -> list[str]:
    """Build the iframe section."""
    total = d['total_iframe_count']
    lines = [
        '-' * 65,
        '3. IFRAMES',
        '-' * 65,
        f'Total Count: {total} {"[OK]" if total == 0 else "[WARNING]"}',
    ]

    if total > 0:
        lines += [
            '',
            'Pendo loses visitor context across iframe boundaries.',
            'Guides/analytics will not work inside cross-origin iframes.',
            '',
            'IFRAME LOCATIONS:',
        ]

        iframe_by_page: dict[str, list] = {}
        for iframe in d['all_iframes']:
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
    return lines


def _section_shadow_dom(d: dict) -> list[str]:
    """Build the shadow DOM section."""
    total = d['total_shadow_roots']
    lines = [
        '-' * 65,
        '4. SHADOW DOM',
        '-' * 65,
        f'Total Shadow Roots: {total} {"[OK]" if total == 0 else "[WARNING]"}',
    ]

    if total > 0:
        lines += [
            '',
            'Pendo cannot pierce Shadow DOM boundaries.',
            'Elements inside shadow roots are invisible to Pendo selectors.',
            '',
            'SHADOW DOM LOCATIONS:',
        ]

        for shadow in d['all_shadow_dom']:
            page_path = get_short_url(shadow.page_url)
            lines.append(f'  Page: {page_path}')
            lines.append(f'    Count: {shadow.count} shadow root(s)')
            if shadow.element_tags:
                lines.append(f'    Elements: {", ".join(shadow.element_tags)}')
            lines.append('')

        lines += [
            'Workaround: Use Track Events API or request engineering expose',
            '            data attributes outside the shadow boundary.',
        ]

    lines.append('')
    return lines


def _section_canvas(d: dict) -> list[str]:
    """Build the canvas section."""
    total = d['total_canvas_count']
    lines = [
        '-' * 65,
        '5. CANVAS ELEMENTS',
        '-' * 65,
        f'Total Count: {total} {"[OK]" if total == 0 else "[INFO]"}',
    ]

    if total > 0:
        lines += [
            '',
            'Canvas renders as pixels; clicks inside are not taggable.',
            'Common uses: Charts, graphs, image editors, maps, games.',
            '',
            'CANVAS LOCATIONS:',
        ]

        for canvas in d['all_canvas']:
            page_path = get_short_url(canvas.page_url)
            lines.append(f'  Page: {page_path}')
            lines.append(f'    Count: {canvas.count} canvas element(s)')
            if canvas.dimensions:
                lines.append(f'    Sizes: {", ".join(canvas.dimensions)}')
            lines.append('')

        lines.append('Workaround: Use Track Events API if canvas interactions need tracking.')

    lines.append('')
    return lines


def _section_selector_suggestions(analyses: list[PageAnalysis]) -> list[str]:
    """Build the selector-suggestion section."""
    all_suggestions: list[SelectorSuggestion] = []
    for a in analyses:
        for ea in (a.buttons, a.inputs, a.links):
            all_suggestions.extend(ea.selector_suggestions)

    # Deduplicate by selector string, keep first occurrence.
    seen_selectors: set[str] = set()
    unique_suggestions: list[SelectorSuggestion] = []
    for s in all_suggestions:
        if s.selector not in seen_selectors:
            seen_selectors.add(s.selector)
            unique_suggestions.append(s)

    lines = [
        '-' * 65,
        '6. SUGGESTED SELECTORS',
        '-' * 65,
    ]

    if not unique_suggestions:
        lines += [
            '[GOOD] All interactive elements have stable IDs or',
            'data-pendo-* attributes. No selector workarounds needed.',
        ]
    else:
        lines += [
            f'{len(unique_suggestions)} selector suggestion(s) for elements',
            'that lack stable IDs. Copy these into Pendo feature rules.',
            '',
        ]

        for conf_level, conf_label in [
            ('excellent', 'EXCELLENT (data-* test attributes)'),
            ('good', 'GOOD (aria-label, :contains, data-*)'),
            ('acceptable', 'ACCEPTABLE (class prefix, name, placeholder)'),
        ]:
            group = [s for s in unique_suggestions if s.confidence == conf_level]
            if not group:
                continue
            lines.append(f'  [{conf_label}]')
            for s in group[:8]:
                lines.append(f'    {s.element_desc}')
                lines.append(f'      -> {s.selector}')
            if len(group) > 8:
                lines.append(f'    ... and {len(group) - 8} more at this confidence level')
            lines.append('')

    lines.append('')
    return lines


def _section_summary(d: dict, analyses: list[PageAnalysis]) -> list[str]:
    """Build the summary and recommendations section."""
    lines = [
        '=' * 65,
        '              SUMMARY & RECOMMENDATIONS',
        '=' * 65,
        f'Overall Risk: {d["risk_level"]}',
        '',
        'TAGGING STRATEGY:',
    ]

    score = d['overall_id_score']
    has_css = d['has_critical_dynamic_css']

    if score >= 80 and not has_css:
        lines += [
            '  [GOOD] Standard Pendo tagging should work well.',
            '  Use IDs as primary selectors where available.',
        ]
    elif score >= 50:
        lines += [
            '  [MODERATE] Mixed approach needed.',
            '  - Use stable IDs where available',
            '  - Use :contains("text") for buttons with clear labels',
            '  - Use [class^="prefix-"] for classes with stable prefixes',
            '  - Request data-pendo-* attrs for critical CTAs',
        ]
    else:
        lines += [
            '  [CHALLENGING] Significant work required.',
            '  - Request engineering add data-pendo-* attributes',
            '  - Use :contains() extensively',
            '  - Avoid CSS class selectors',
            '  - Consider Track Events API for complex elements',
        ]

    lines.append('')

    # Key concerns
    concerns = []
    if d['button_id_score'] < 70:
        concerns.append(f'Low button ID stability ({d["button_id_score"]:.0f}%)')
    if has_css:
        concerns.append(f'Dynamic CSS classes detected ({d["total_dynamic_classes"]} found)')
    if d['total_shadow_roots'] > 0:
        pages_with_shadow = [get_short_url(s.page_url) for s in d['all_shadow_dom']]
        concerns.append(f'Shadow DOM on: {", ".join(pages_with_shadow[:3])}')
    if d['total_iframe_count'] > 2:
        concerns.append(f'Multiple iframes ({d["total_iframe_count"]})')

    if concerns:
        lines.append('KEY CONCERNS:')
        for c in concerns:
            lines.append(f'  * {c}')
        lines.append('')

    # Positive indicators
    positives = []
    if d['pendo_attr_buttons'] > 0 or d['pendo_attr_inputs'] > 0:
        positives.append(f'data-pendo-* attributes already in use ({d["pendo_attr_buttons"] + d["pendo_attr_inputs"]} elements)')
    if d['stable_button_ids'] > 0:
        positives.append(f'{d["stable_button_ids"]} buttons have stable IDs')
    if d['text_content_buttons'] > 0:
        positives.append(f'{d["text_content_buttons"]} buttons have text (can use :contains)')

    if positives:
        lines.append('POSITIVE INDICATORS:')
        for p in positives:
            lines.append(f'  + {p}')
        lines.append('')

    # Next steps
    lines.append('RECOMMENDED NEXT STEPS:')
    if score < 80 or has_css:
        lines += [
            '  1. Share this report with customer engineering team',
            '  2. Request data-pendo-* attributes on key CTAs',
            '  3. Identify elements that can use :contains() workaround',
            '  4. Plan for Track Events API where needed',
        ]
    else:
        lines += [
            '  1. Proceed with standard Pendo implementation',
            '  2. Prioritise ID-based selectors',
            '  3. Test feature tags after deployment',
        ]

    lines += ['', '=' * 65]

    # Page list
    lines += ['', 'Pages Scanned:']
    for i, a in enumerate(analyses, 1):
        short = a.url[:60] + '...' if len(a.url) > 60 else a.url
        lines.append(f'  {i}. {short}')

    return lines


# ---------------------------------------------------------------------------
# Public report generators
# ---------------------------------------------------------------------------

def generate_report(url: str, analyses: list[PageAnalysis], software: SoftwareDetection) -> str:
    """Generate the human-readable feasibility report."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')

    d = _aggregate_data(analyses)
    d = _calculate_scores(d)

    lines: list[str] = []
    lines += _section_header(d, url, timestamp, len(analyses))
    lines += _section_dynamic_css_warning(d)
    lines += _section_software(software)
    lines += _section_id_analysis(d)
    lines += _section_css_classes(d)
    lines += _section_iframes(d)
    lines += _section_shadow_dom(d)
    lines += _section_canvas(d)
    lines += _section_selector_suggestions(analyses)
    lines += _section_summary(d, analyses)

    return '\n'.join(lines)


def _element_analysis_to_dict(ea: ElementAnalysis) -> dict:
    """Convert an ElementAnalysis to a JSON-serialisable dict."""
    d = dict(ea.__dict__)
    # Convert SelectorSuggestion dataclasses to plain dicts.
    d['selector_suggestions'] = [s.__dict__ for s in ea.selector_suggestions]
    return d


def generate_json_report(url: str, analyses: list[PageAnalysis], software: SoftwareDetection) -> dict:
    """Generate a JSON report for programmatic use."""
    domain = urlparse(url).netloc

    pages_data = []
    for analysis in analyses:
        page_dict = {
            'url': analysis.url,
            'buttons': _element_analysis_to_dict(analysis.buttons),
            'inputs': _element_analysis_to_dict(analysis.inputs),
            'links': _element_analysis_to_dict(analysis.links),
            'dynamic_class_count': analysis.dynamic_class_count,
            'dynamic_class_examples': analysis.dynamic_class_examples,
            'iframes': [
                {'src': i.src, 'page_url': i.page_url, 'is_cross_origin': i.is_cross_origin}
                for i in analysis.iframes
            ],
            'shadow_dom': {
                'count': analysis.shadow_dom.count,
                'page_url': analysis.shadow_dom.page_url,
                'element_tags': analysis.shadow_dom.element_tags,
            } if analysis.shadow_dom else None,
            'canvas': {
                'count': analysis.canvas.count,
                'page_url': analysis.canvas.page_url,
                'dimensions': analysis.canvas.dimensions,
            } if analysis.canvas else None,
        }
        pages_data.append(page_dict)

    return {
        'meta': {
            'site': url,
            'domain': domain,
            'pages_analysed': len(analyses),
            'timestamp': datetime.now().isoformat(),
        },
        'software': {
            'frontend_frameworks': software.frontend_frameworks,
            'css_frameworks': software.css_frameworks,
            'analytics_tools': software.analytics_tools,
            'other_tools': software.other_tools,
            'meta_generator': software.meta_generator,
        },
        'pages': pages_data,
    }
