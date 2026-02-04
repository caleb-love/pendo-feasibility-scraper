"""Tests for report generation functions."""

import json
import pytest
from pendo_feasibility_scraper import (
    generate_report,
    generate_json_report,
    PageAnalysis,
    ElementAnalysis,
    SoftwareDetection,
    IframeInfo,
    ShadowDOMInfo,
    CanvasInfo,
)


@pytest.fixture
def simple_page_analysis():
    """Create a simple page analysis for testing."""
    buttons = ElementAnalysis()
    buttons.total = 5
    buttons.stable_ids = 3
    buttons.dynamic_ids = 1
    buttons.no_ids = 1
    buttons.has_pendo_attr = 1
    buttons.has_text_content = 4
    buttons.stable_id_examples = ['submit-btn', 'cancel-btn']
    buttons.dynamic_id_examples = [('react-select-1-input', 'React Select instance ID')]
    buttons.pendo_attr_examples = ['data-pendo-id="cta"']

    inputs = ElementAnalysis()
    inputs.total = 3
    inputs.stable_ids = 2
    inputs.no_ids = 1

    links = ElementAnalysis()
    links.total = 10
    links.stable_ids = 8

    analysis = PageAnalysis(url='https://example.com')
    analysis.buttons = buttons
    analysis.inputs = inputs
    analysis.links = links
    analysis.dynamic_class_count = 3
    analysis.dynamic_class_examples = [
        ('btn-abc123', 'Dynamic hash suffix [prefix: btn]'),
        ('sc-aXZVg', 'Styled Components hash [NO stable prefix]'),
    ]

    return analysis


@pytest.fixture
def simple_software_detection():
    """Create simple software detection for testing."""
    detection = SoftwareDetection()
    detection.frontend_frameworks = ['React', 'Next.js']
    detection.css_frameworks = ['Material UI']
    detection.analytics_tools = ['Segment', 'Heap']
    return detection


class TestGenerateReport:
    """Tests for text report generation."""

    def test_report_contains_header(self, simple_page_analysis, simple_software_detection):
        """Report should contain header with title."""
        report = generate_report(
            'https://example.com',
            [simple_page_analysis],
            simple_software_detection
        )

        assert 'PENDO FEASIBILITY REPORT' in report

    def test_report_contains_site_url(self, simple_page_analysis, simple_software_detection):
        """Report should contain the site URL."""
        report = generate_report(
            'https://example.com',
            [simple_page_analysis],
            simple_software_detection
        )

        assert 'Site: https://example.com' in report

    def test_report_contains_page_count(self, simple_page_analysis, simple_software_detection):
        """Report should contain page count."""
        report = generate_report(
            'https://example.com',
            [simple_page_analysis],
            simple_software_detection
        )

        assert 'Pages Analysed: 1' in report

    def test_report_contains_software_detection(self, simple_page_analysis, simple_software_detection):
        """Report should list detected software."""
        report = generate_report(
            'https://example.com',
            [simple_page_analysis],
            simple_software_detection
        )

        assert 'DETECTED SOFTWARE' in report
        assert 'React' in report
        assert 'Next.js' in report
        assert 'Material UI' in report
        assert 'Segment' in report

    def test_report_contains_button_analysis(self, simple_page_analysis, simple_software_detection):
        """Report should contain button analysis."""
        report = generate_report(
            'https://example.com',
            [simple_page_analysis],
            simple_software_detection
        )

        assert 'BUTTONS' in report
        assert 'Total: 5' in report
        assert 'With stable IDs: 3' in report

    def test_report_contains_input_analysis(self, simple_page_analysis, simple_software_detection):
        """Report should contain input analysis."""
        report = generate_report(
            'https://example.com',
            [simple_page_analysis],
            simple_software_detection
        )

        assert 'INPUTS' in report
        assert 'Total: 3' in report

    def test_report_contains_dynamic_css_warning(self, simple_page_analysis, simple_software_detection):
        """Report should warn about dynamic CSS classes."""
        report = generate_report(
            'https://example.com',
            [simple_page_analysis],
            simple_software_detection
        )

        assert 'CRITICAL' in report or 'CSS CLASS ANALYSIS' in report

    def test_report_contains_recommendations(self, simple_page_analysis, simple_software_detection):
        """Report should contain recommendations."""
        report = generate_report(
            'https://example.com',
            [simple_page_analysis],
            simple_software_detection
        )

        assert 'SUMMARY & RECOMMENDATIONS' in report

    def test_report_contains_example_ids(self, simple_page_analysis, simple_software_detection):
        """Report should show example stable IDs."""
        report = generate_report(
            'https://example.com',
            [simple_page_analysis],
            simple_software_detection
        )

        assert 'submit-btn' in report or 'cancel-btn' in report

    def test_report_shows_pendo_attributes(self, simple_page_analysis, simple_software_detection):
        """Report should highlight pendo attributes when present."""
        report = generate_report(
            'https://example.com',
            [simple_page_analysis],
            simple_software_detection
        )

        assert 'data-pendo' in report or 'EXCELLENT' in report


class TestGenerateReportRiskLevels:
    """Tests for risk level calculation in reports."""

    def test_low_risk_report(self, simple_software_detection):
        """High ID stability should result in low risk."""
        # All elements have stable IDs
        buttons = ElementAnalysis()
        buttons.total = 10
        buttons.stable_ids = 10

        inputs = ElementAnalysis()
        inputs.total = 5
        inputs.stable_ids = 5

        analysis = PageAnalysis(url='https://example.com')
        analysis.buttons = buttons
        analysis.inputs = inputs
        analysis.dynamic_class_count = 0

        report = generate_report('https://example.com', [analysis], simple_software_detection)

        assert 'Risk Level: LOW' in report

    def test_high_risk_with_no_stable_ids(self, simple_software_detection):
        """No stable IDs should result in higher risk."""
        buttons = ElementAnalysis()
        buttons.total = 10
        buttons.dynamic_ids = 10

        inputs = ElementAnalysis()
        inputs.total = 5
        inputs.no_ids = 5

        analysis = PageAnalysis(url='https://example.com')
        analysis.buttons = buttons
        analysis.inputs = inputs
        analysis.dynamic_class_count = 50
        analysis.dynamic_class_examples = [('test', 'reason')]

        report = generate_report('https://example.com', [analysis], simple_software_detection)

        assert 'HIGH' in report or 'MODERATE' in report

    def test_shadow_dom_increases_risk(self, simple_software_detection):
        """Shadow DOM presence should increase risk."""
        buttons = ElementAnalysis()
        buttons.total = 10
        buttons.stable_ids = 10

        analysis = PageAnalysis(url='https://example.com')
        analysis.buttons = buttons
        analysis.shadow_dom = ShadowDOMInfo(
            count=5,
            page_url='https://example.com',
            element_tags=['custom-element']
        )

        report = generate_report('https://example.com', [analysis], simple_software_detection)

        assert 'SHADOW DOM' in report
        assert 'Shadow Roots: 5' in report or 'Total Shadow Roots: 5' in report


class TestGenerateReportIframes:
    """Tests for iframe reporting."""

    def test_report_shows_iframes(self, simple_software_detection):
        """Report should show iframe information."""
        buttons = ElementAnalysis()
        buttons.total = 5
        buttons.stable_ids = 5

        analysis = PageAnalysis(url='https://example.com')
        analysis.buttons = buttons
        analysis.iframes = [
            IframeInfo(src='https://other.com/embed', page_url='https://example.com', is_cross_origin=True),
            IframeInfo(src='https://example.com/frame', page_url='https://example.com', is_cross_origin=False),
        ]

        report = generate_report('https://example.com', [analysis], simple_software_detection)

        assert 'IFRAMES' in report
        assert 'Total Count: 2' in report

    def test_report_marks_cross_origin(self, simple_software_detection):
        """Report should mark cross-origin iframes."""
        buttons = ElementAnalysis()
        buttons.total = 5
        buttons.stable_ids = 5

        analysis = PageAnalysis(url='https://example.com')
        analysis.buttons = buttons
        analysis.iframes = [
            IframeInfo(src='https://other.com/embed', page_url='https://example.com', is_cross_origin=True),
        ]

        report = generate_report('https://example.com', [analysis], simple_software_detection)

        assert 'CROSS-ORIGIN' in report


class TestGenerateReportCanvas:
    """Tests for canvas reporting."""

    def test_report_shows_canvas(self, simple_software_detection):
        """Report should show canvas information."""
        buttons = ElementAnalysis()
        buttons.total = 5
        buttons.stable_ids = 5

        analysis = PageAnalysis(url='https://example.com')
        analysis.buttons = buttons
        analysis.canvas = CanvasInfo(
            count=2,
            page_url='https://example.com',
            dimensions=['800x600', '400x300']
        )

        report = generate_report('https://example.com', [analysis], simple_software_detection)

        assert 'CANVAS' in report
        assert 'Total Count: 2' in report


class TestGenerateJsonReport:
    """Tests for JSON report generation."""

    def test_json_report_structure(self, simple_page_analysis, simple_software_detection):
        """JSON report should have correct structure."""
        report = generate_json_report(
            'https://example.com',
            [simple_page_analysis],
            simple_software_detection
        )

        assert 'meta' in report
        assert 'software' in report
        assert 'pages' in report

    def test_json_report_meta(self, simple_page_analysis, simple_software_detection):
        """JSON report meta should contain site info."""
        report = generate_json_report(
            'https://example.com',
            [simple_page_analysis],
            simple_software_detection
        )

        assert report['meta']['site'] == 'https://example.com'
        assert report['meta']['domain'] == 'example.com'
        assert report['meta']['pages_analysed'] == 1
        assert 'timestamp' in report['meta']

    def test_json_report_software(self, simple_page_analysis, simple_software_detection):
        """JSON report should include software detection."""
        report = generate_json_report(
            'https://example.com',
            [simple_page_analysis],
            simple_software_detection
        )

        assert report['software']['frontend_frameworks'] == ['React', 'Next.js']
        assert report['software']['css_frameworks'] == ['Material UI']
        assert report['software']['analytics_tools'] == ['Segment', 'Heap']

    def test_json_report_pages(self, simple_page_analysis, simple_software_detection):
        """JSON report should include page analysis."""
        report = generate_json_report(
            'https://example.com',
            [simple_page_analysis],
            simple_software_detection
        )

        assert len(report['pages']) == 1
        page = report['pages'][0]
        assert page['url'] == 'https://example.com'
        assert 'buttons' in page
        assert 'inputs' in page
        assert 'links' in page

    def test_json_report_element_details(self, simple_page_analysis, simple_software_detection):
        """JSON report should include element analysis details."""
        report = generate_json_report(
            'https://example.com',
            [simple_page_analysis],
            simple_software_detection
        )

        buttons = report['pages'][0]['buttons']
        assert buttons['total'] == 5
        assert buttons['stable_ids'] == 3
        assert buttons['dynamic_ids'] == 1

    def test_json_report_serializable(self, simple_page_analysis, simple_software_detection):
        """JSON report should be fully serializable."""
        report = generate_json_report(
            'https://example.com',
            [simple_page_analysis],
            simple_software_detection
        )

        # Should not raise - verifies all data is JSON-serializable
        serialized = json.dumps(report)
        deserialized = json.loads(serialized)

        # Verify structure is preserved (note: tuples become lists in JSON)
        assert deserialized['meta']['site'] == report['meta']['site']
        assert deserialized['meta']['pages_analysed'] == report['meta']['pages_analysed']
        assert len(deserialized['pages']) == len(report['pages'])

    def test_json_report_with_iframes(self, simple_software_detection):
        """JSON report should include iframe data."""
        analysis = PageAnalysis(url='https://example.com')
        analysis.iframes = [
            IframeInfo(src='https://other.com/embed', page_url='https://example.com', is_cross_origin=True),
        ]

        report = generate_json_report(
            'https://example.com',
            [analysis],
            simple_software_detection
        )

        assert len(report['pages'][0]['iframes']) == 1
        iframe = report['pages'][0]['iframes'][0]
        assert iframe['src'] == 'https://other.com/embed'
        assert iframe['is_cross_origin'] is True

    def test_json_report_with_shadow_dom(self, simple_software_detection):
        """JSON report should include shadow DOM data."""
        analysis = PageAnalysis(url='https://example.com')
        analysis.shadow_dom = ShadowDOMInfo(
            count=2,
            page_url='https://example.com',
            element_tags=['custom-el']
        )

        report = generate_json_report(
            'https://example.com',
            [analysis],
            simple_software_detection
        )

        shadow = report['pages'][0]['shadow_dom']
        assert shadow['count'] == 2
        assert shadow['element_tags'] == ['custom-el']

    def test_json_report_with_canvas(self, simple_software_detection):
        """JSON report should include canvas data."""
        analysis = PageAnalysis(url='https://example.com')
        analysis.canvas = CanvasInfo(
            count=1,
            page_url='https://example.com',
            dimensions=['800x600']
        )

        report = generate_json_report(
            'https://example.com',
            [analysis],
            simple_software_detection
        )

        canvas = report['pages'][0]['canvas']
        assert canvas['count'] == 1
        assert canvas['dimensions'] == ['800x600']


class TestMultiPageReport:
    """Tests for reports with multiple pages."""

    def test_aggregates_across_pages(self, simple_software_detection):
        """Report should aggregate data across multiple pages."""
        pages = []
        for i in range(3):
            buttons = ElementAnalysis()
            buttons.total = 5
            buttons.stable_ids = 3

            analysis = PageAnalysis(url=f'https://example.com/page{i}')
            analysis.buttons = buttons
            pages.append(analysis)

        report = generate_report('https://example.com', pages, simple_software_detection)

        assert 'Pages Analysed: 3' in report
        # Total buttons should be 15 (5 * 3)
        assert 'Total: 15' in report

    def test_json_includes_all_pages(self, simple_software_detection):
        """JSON report should include all page analyses."""
        pages = []
        for i in range(3):
            analysis = PageAnalysis(url=f'https://example.com/page{i}')
            pages.append(analysis)

        report = generate_json_report('https://example.com', pages, simple_software_detection)

        assert report['meta']['pages_analysed'] == 3
        assert len(report['pages']) == 3
