"""Pendo Feasibility Scraper – core package.

Re-exports all public symbols so consumers can do:
    from scraper import run_scan, ScrapeConfig
or continue using the top-level module:
    from pendo_feasibility_scraper import run_scan, ScrapeConfig
"""

# Models
from .models import (  # noqa: F401
    SelectorSuggestion,
    ElementAnalysis,
    IframeInfo,
    ShadowDOMInfo,
    CanvasInfo,
    SoftwareDetection,
    PageAnalysis,
    ScrapeConfig,
    ScanResult,
)

# Pattern checking
from .patterns import (  # noqa: F401
    DYNAMIC_ID_PATTERNS,
    DYNAMIC_CLASS_PATTERNS,
    SOFTWARE_SIGNATURES,
    check_dynamic_id,
    check_dynamic_class,
)

# Analysis
from .analysis import (  # noqa: F401
    suggest_selector,
    analyse_element,
    analyse_dynamic_classes,
    detect_software,
    analyse_iframes,
    detect_shadow_dom,
    analyse_canvas,
)

# URL utilities
from .url_utils import (  # noqa: F401
    url_allowed,
    extract_internal_links,
)

# Page helpers
from .page_helpers import (  # noqa: F401
    scroll_page,
    dismiss_popups,
    analyse_page,
)

# Reporting
from .reporting import (  # noqa: F401
    get_short_url,
    generate_report,
    generate_json_report,
)

# Login
from .login import apply_login  # noqa: F401

# Scanner
from .scanner import run_scan  # noqa: F401
