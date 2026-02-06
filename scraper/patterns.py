"""Pre-compiled pattern tables and checkers for dynamic IDs/classes.

Also contains software detection signature tables and the skip-extension
set used during link extraction.
"""

import re


# ---------------------------------------------------------------------------
# Dynamic ID patterns – these are PROBLEMATIC for Pendo.
# Each entry: (compiled_regex, label, reason, has_stable_prefix)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Dynamic CLASS patterns
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Software detection signatures
# ---------------------------------------------------------------------------

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
_SKIP_EXTENSIONS = frozenset([
    '.pdf', '.jpg', '.jpeg', '.png', '.gif', '.css', '.js', '.svg',
    '.ico', '.woff', '.woff2', '.ttf', '.eot', '.mp4', '.webm',
])


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
