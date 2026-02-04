"""Tests for utility functions in the scraper."""

import pytest
from pendo_feasibility_scraper import (
    url_allowed,
    get_short_url,
    ScrapeConfig,
    ElementAnalysis,
    PageAnalysis,
    SoftwareDetection,
    IframeInfo,
    ShadowDOMInfo,
    CanvasInfo,
)


class TestUrlAllowed:
    """Tests for URL allow/deny filtering."""

    def test_no_patterns_allows_all(self):
        """With no patterns, all URLs should be allowed."""
        assert url_allowed('https://example.com/any/path', [], []) is True
        assert url_allowed('https://test.com', [], []) is True

    def test_denylist_blocks_matching(self):
        """URLs matching denylist patterns should be blocked."""
        denylist = [r'/admin/', r'/api/']

        assert url_allowed('https://example.com/admin/users', [], denylist) is False
        assert url_allowed('https://example.com/api/v1', [], denylist) is False
        assert url_allowed('https://example.com/app/', [], denylist) is True

    def test_allowlist_only_allows_matching(self):
        """With allowlist, only matching URLs should be allowed."""
        allowlist = [r'/app/', r'/dashboard/']

        assert url_allowed('https://example.com/app/home', allowlist, []) is True
        assert url_allowed('https://example.com/dashboard/', allowlist, []) is True
        assert url_allowed('https://example.com/login', allowlist, []) is False

    def test_denylist_takes_precedence(self):
        """Denylist should take precedence over allowlist."""
        allowlist = [r'/app/']
        denylist = [r'/app/admin']

        assert url_allowed('https://example.com/app/home', allowlist, denylist) is True
        assert url_allowed('https://example.com/app/admin', allowlist, denylist) is False

    def test_regex_patterns(self):
        """Regex patterns should work correctly."""
        allowlist = [r'^https://example\.com/v\d+/']

        assert url_allowed('https://example.com/v1/api', allowlist, []) is True
        assert url_allowed('https://example.com/v2/api', allowlist, []) is True
        assert url_allowed('https://example.com/api', allowlist, []) is False

    def test_case_insensitive(self):
        """Pattern matching should be case insensitive."""
        denylist = [r'/admin/']

        assert url_allowed('https://example.com/Admin/', [], denylist) is False
        assert url_allowed('https://example.com/ADMIN/', [], denylist) is False


class TestGetShortUrl:
    """Tests for URL shortening display function."""

    def test_short_url_unchanged(self):
        """Short URLs should not be modified."""
        assert get_short_url('https://example.com/path') == '/path'

    def test_long_url_truncated(self):
        """Long URLs should be truncated."""
        long_path = '/very/long/path/that/exceeds/the/maximum/length/limit/for/display'
        result = get_short_url(f'https://example.com{long_path}', max_len=30)

        assert len(result) == 30
        assert result.startswith('...')

    def test_root_path(self):
        """Root path should return '/'."""
        assert get_short_url('https://example.com') == '/'
        assert get_short_url('https://example.com/') == '/'

    def test_custom_max_length(self):
        """Custom max length should be respected."""
        result = get_short_url('https://example.com/path/to/page', max_len=10)
        assert len(result) <= 10


class TestDataClasses:
    """Tests for dataclass initialization and defaults."""

    def test_element_analysis_defaults(self):
        """ElementAnalysis should have proper defaults."""
        analysis = ElementAnalysis()

        assert analysis.total == 0
        assert analysis.stable_ids == 0
        assert analysis.dynamic_ids == 0
        assert analysis.no_ids == 0
        assert analysis.has_pendo_attr == 0
        assert analysis.has_data_attr == 0
        assert analysis.has_text_content == 0
        assert analysis.dynamic_id_examples == []
        assert analysis.stable_id_examples == []
        assert analysis.pendo_attr_examples == []
        assert analysis.dynamic_class_examples == []

    def test_page_analysis_defaults(self):
        """PageAnalysis should have proper defaults."""
        analysis = PageAnalysis(url='https://example.com')

        assert analysis.url == 'https://example.com'
        assert isinstance(analysis.buttons, ElementAnalysis)
        assert isinstance(analysis.inputs, ElementAnalysis)
        assert isinstance(analysis.links, ElementAnalysis)
        assert analysis.dynamic_class_count == 0
        assert analysis.dynamic_class_examples == []
        assert analysis.iframes == []
        assert analysis.shadow_dom is None
        assert analysis.canvas is None

    def test_software_detection_defaults(self):
        """SoftwareDetection should have proper defaults."""
        detection = SoftwareDetection()

        assert detection.frontend_frameworks == []
        assert detection.css_frameworks == []
        assert detection.analytics_tools == []
        assert detection.other_tools == []
        assert detection.meta_generator == ''

    def test_scrape_config_defaults(self):
        """ScrapeConfig should have proper defaults."""
        config = ScrapeConfig()

        assert config.max_links == 20
        assert config.max_pages == 12
        assert config.headless is True
        assert config.viewport_width == 1920
        assert config.viewport_height == 1080
        assert config.wait_until == 'domcontentloaded'
        assert config.navigation_timeout_ms == 30000
        assert config.include_query_params is False
        assert config.allowlist_patterns == []
        assert config.denylist_patterns == []
        assert config.login_mode == 'manual'
        assert config.dismiss_popups is True
        assert config.scroll_pages is True

    def test_iframe_info(self):
        """IframeInfo should store all properties."""
        iframe = IframeInfo(
            src='https://example.com/iframe',
            page_url='https://example.com',
            is_cross_origin=False
        )

        assert iframe.src == 'https://example.com/iframe'
        assert iframe.page_url == 'https://example.com'
        assert iframe.is_cross_origin is False

    def test_shadow_dom_info(self):
        """ShadowDOMInfo should store all properties."""
        shadow = ShadowDOMInfo(
            count=3,
            page_url='https://example.com',
            element_tags=['custom-element', 'web-component']
        )

        assert shadow.count == 3
        assert shadow.page_url == 'https://example.com'
        assert shadow.element_tags == ['custom-element', 'web-component']

    def test_canvas_info(self):
        """CanvasInfo should store all properties."""
        canvas = CanvasInfo(
            count=2,
            page_url='https://example.com',
            dimensions=['800x600', '400x300']
        )

        assert canvas.count == 2
        assert canvas.page_url == 'https://example.com'
        assert canvas.dimensions == ['800x600', '400x300']


class TestScrapeConfigCustomization:
    """Tests for ScrapeConfig with custom values."""

    def test_custom_config(self):
        """ScrapeConfig should accept custom values."""
        config = ScrapeConfig(
            max_links=50,
            max_pages=25,
            headless=False,
            viewport_width=1280,
            viewport_height=720,
            login_mode='credentials',
            allowlist_patterns=['/app/'],
            denylist_patterns=['/admin/']
        )

        assert config.max_links == 50
        assert config.max_pages == 25
        assert config.headless is False
        assert config.viewport_width == 1280
        assert config.login_mode == 'credentials'
        assert config.allowlist_patterns == ['/app/']
        assert config.denylist_patterns == ['/admin/']

    def test_login_credentials_config(self):
        """ScrapeConfig should store login credentials."""
        config = ScrapeConfig(
            login_mode='credentials',
            login_url='https://example.com/login',
            username_selector='#username',
            password_selector='#password',
            submit_selector='#submit',
            username='user@example.com',
            password='secret'
        )

        assert config.login_mode == 'credentials'
        assert config.login_url == 'https://example.com/login'
        assert config.username_selector == '#username'
        assert config.password_selector == '#password'
        assert config.submit_selector == '#submit'
        assert config.username == 'user@example.com'
        assert config.password == 'secret'
