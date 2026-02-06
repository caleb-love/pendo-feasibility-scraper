"""Data classes used throughout the scraper.

All structured types for analysis results, configuration, and scan output
live here so they can be imported cleanly by every other module.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SelectorSuggestion:
    """A recommended Pendo CSS selector for a specific element."""
    element_desc: str   # Human-readable description (e.g., 'Button "Submit Order"')
    selector: str       # The CSS selector to use in Pendo
    method: str         # Technique used: data-pendo, id, data-attr, aria-label, contains, class-prefix, attribute
    confidence: str     # excellent, good, acceptable


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
    selector_suggestions: list = field(default_factory=list)  # List[SelectorSuggestion]


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
