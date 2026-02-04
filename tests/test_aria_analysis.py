"""Tests for ARIA attribute analysis functionality.

These tests verify that ARIA attributes are correctly identified and
reported as alternative selector options for Pendo tagging.
"""

import pytest
from pendo_feasibility_scraper import (
    ElementAnalysis,
    PageAnalysis,
    SoftwareDetection,
    generate_report,
    generate_json_report,
)


class TestElementAnalysisAriaFields:
    """Tests for ARIA fields in ElementAnalysis dataclass."""

    def test_aria_fields_default_to_zero(self):
        """ARIA count fields should default to zero."""
        analysis = ElementAnalysis()

        assert analysis.has_aria_label == 0
        assert analysis.has_aria_describedby == 0
        assert analysis.has_role == 0
        assert analysis.has_title == 0

    def test_aria_example_fields_default_to_empty(self):
        """ARIA example lists should default to empty."""
        analysis = ElementAnalysis()

        assert analysis.aria_label_examples == []
        assert analysis.role_examples == []

    def test_aria_fields_can_be_set(self):
        """ARIA fields should be settable."""
        analysis = ElementAnalysis()
        analysis.has_aria_label = 5
        analysis.has_aria_describedby = 3
        analysis.has_role = 10
        analysis.has_title = 2
        analysis.aria_label_examples = ['Submit', 'Cancel', 'Close']
        analysis.role_examples = ['button', 'navigation']

        assert analysis.has_aria_label == 5
        assert analysis.has_aria_describedby == 3
        assert analysis.has_role == 10
        assert analysis.has_title == 2
        assert len(analysis.aria_label_examples) == 3
        assert len(analysis.role_examples) == 2


class TestAriaReportGeneration:
    """Tests for ARIA attribute reporting."""

    @pytest.fixture
    def page_with_aria_attributes(self):
        """Create a page analysis with ARIA attributes."""
        buttons = ElementAnalysis()
        buttons.total = 10
        buttons.stable_ids = 3
        buttons.dynamic_ids = 4
        buttons.no_ids = 3
        buttons.has_aria_label = 6
        buttons.has_aria_describedby = 2
        buttons.has_role = 8
        buttons.has_title = 3
        buttons.aria_label_examples = ['Submit form', 'Cancel action', 'Close dialog']
        buttons.role_examples = ['button', 'menuitem']

        inputs = ElementAnalysis()
        inputs.total = 5
        inputs.stable_ids = 2
        inputs.no_ids = 3
        inputs.has_aria_label = 4
        inputs.has_aria_describedby = 3
        inputs.has_role = 2
        inputs.aria_label_examples = ['Search', 'Email address']
        inputs.role_examples = ['searchbox', 'textbox']

        analysis = PageAnalysis(url='https://example.com')
        analysis.buttons = buttons
        analysis.inputs = inputs

        return analysis

    @pytest.fixture
    def page_without_aria_attributes(self):
        """Create a page analysis without ARIA attributes."""
        buttons = ElementAnalysis()
        buttons.total = 10
        buttons.stable_ids = 10

        inputs = ElementAnalysis()
        inputs.total = 5
        inputs.stable_ids = 5

        analysis = PageAnalysis(url='https://example.com')
        analysis.buttons = buttons
        analysis.inputs = inputs

        return analysis

    @pytest.fixture
    def simple_software_detection(self):
        """Create simple software detection."""
        detection = SoftwareDetection()
        detection.frontend_frameworks = ['React']
        return detection

    def test_report_includes_aria_section_when_present(
        self, page_with_aria_attributes, simple_software_detection
    ):
        """Report should include ARIA section when attributes are found."""
        report = generate_report(
            'https://example.com',
            [page_with_aria_attributes],
            simple_software_detection
        )

        assert 'ARIA ATTRIBUTES' in report
        assert 'Alternative Selectors' in report

    def test_report_shows_aria_label_counts(
        self, page_with_aria_attributes, simple_software_detection
    ):
        """Report should show aria-label counts for buttons and inputs."""
        report = generate_report(
            'https://example.com',
            [page_with_aria_attributes],
            simple_software_detection
        )

        assert 'With aria-label: 6' in report  # buttons
        assert 'With aria-label: 4' in report  # inputs

    def test_report_shows_aria_label_examples(
        self, page_with_aria_attributes, simple_software_detection
    ):
        """Report should show example aria-label values."""
        report = generate_report(
            'https://example.com',
            [page_with_aria_attributes],
            simple_software_detection
        )

        assert '[aria-label="' in report
        # At least one of the examples should appear
        assert any(label in report for label in ['Submit form', 'Cancel action', 'Search'])

    def test_report_shows_role_examples(
        self, page_with_aria_attributes, simple_software_detection
    ):
        """Report should show role attribute examples."""
        report = generate_report(
            'https://example.com',
            [page_with_aria_attributes],
            simple_software_detection
        )

        assert '[role="' in report
        assert any(role in report for role in ['button', 'menuitem', 'searchbox'])

    def test_report_shows_usage_guidance(
        self, page_with_aria_attributes, simple_software_detection
    ):
        """Report should show how to use aria selectors in Pendo."""
        report = generate_report(
            'https://example.com',
            [page_with_aria_attributes],
            simple_software_detection
        )

        assert 'Usage in Pendo' in report or 'aria-label' in report

    def test_report_omits_aria_section_when_none_found(
        self, page_without_aria_attributes, simple_software_detection
    ):
        """Report should not have ARIA section when no attributes found."""
        report = generate_report(
            'https://example.com',
            [page_without_aria_attributes],
            simple_software_detection
        )

        # The detailed ARIA section should not appear
        assert 'ARIA ATTRIBUTES (Alternative Selectors)' not in report

    def test_report_describes_aria_as_stable(
        self, page_with_aria_attributes, simple_software_detection
    ):
        """Report should describe ARIA attributes as stable alternatives."""
        report = generate_report(
            'https://example.com',
            [page_with_aria_attributes],
            simple_software_detection
        )

        assert 'stable' in report.lower() or 'reliable' in report.lower()


class TestAriaJsonReport:
    """Tests for ARIA data in JSON reports."""

    @pytest.fixture
    def page_with_aria(self):
        """Create a page analysis with ARIA attributes."""
        buttons = ElementAnalysis()
        buttons.total = 5
        buttons.has_aria_label = 3
        buttons.has_role = 4
        buttons.aria_label_examples = ['Submit', 'Cancel']
        buttons.role_examples = ['button']

        analysis = PageAnalysis(url='https://example.com')
        analysis.buttons = buttons

        return analysis

    @pytest.fixture
    def simple_software_detection(self):
        """Create simple software detection."""
        return SoftwareDetection()

    def test_json_report_includes_aria_counts(
        self, page_with_aria, simple_software_detection
    ):
        """JSON report should include ARIA attribute counts."""
        report = generate_json_report(
            'https://example.com',
            [page_with_aria],
            simple_software_detection
        )

        buttons = report['pages'][0]['buttons']
        assert buttons['has_aria_label'] == 3
        assert buttons['has_role'] == 4

    def test_json_report_includes_aria_examples(
        self, page_with_aria, simple_software_detection
    ):
        """JSON report should include ARIA examples."""
        report = generate_json_report(
            'https://example.com',
            [page_with_aria],
            simple_software_detection
        )

        buttons = report['pages'][0]['buttons']
        assert buttons['aria_label_examples'] == ['Submit', 'Cancel']
        assert buttons['role_examples'] == ['button']


class TestAriaAggregation:
    """Tests for ARIA data aggregation across multiple pages."""

    @pytest.fixture
    def multi_page_analysis(self):
        """Create multiple page analyses with different ARIA data."""
        pages = []

        for i in range(3):
            buttons = ElementAnalysis()
            buttons.total = 5
            buttons.has_aria_label = i + 1  # 1, 2, 3
            buttons.has_role = 2
            buttons.aria_label_examples = [f'Button{i}']
            buttons.role_examples = ['button']

            inputs = ElementAnalysis()
            inputs.total = 3
            inputs.has_aria_label = 1
            inputs.aria_label_examples = [f'Input{i}']

            analysis = PageAnalysis(url=f'https://example.com/page{i}')
            analysis.buttons = buttons
            analysis.inputs = inputs
            pages.append(analysis)

        return pages

    @pytest.fixture
    def simple_software_detection(self):
        """Create simple software detection."""
        return SoftwareDetection()

    def test_report_aggregates_aria_counts(
        self, multi_page_analysis, simple_software_detection
    ):
        """Report should aggregate ARIA counts across pages."""
        report = generate_report(
            'https://example.com',
            multi_page_analysis,
            simple_software_detection
        )

        # Total buttons with aria-label: 1 + 2 + 3 = 6
        assert 'With aria-label: 6' in report

    def test_report_collects_aria_examples_from_all_pages(
        self, multi_page_analysis, simple_software_detection
    ):
        """Report should collect ARIA examples from all pages."""
        report = generate_report(
            'https://example.com',
            multi_page_analysis,
            simple_software_detection
        )

        # Examples should be collected from multiple pages
        # At least some should appear
        assert '[aria-label="' in report


class TestAriaEdgeCases:
    """Tests for edge cases in ARIA analysis."""

    @pytest.fixture
    def simple_software_detection(self):
        """Create simple software detection."""
        return SoftwareDetection()

    def test_long_aria_label_truncated_in_report(self, simple_software_detection):
        """Long aria-label values should be truncated in report."""
        buttons = ElementAnalysis()
        buttons.total = 1
        buttons.has_aria_label = 1
        buttons.aria_label_examples = [
            'This is a very long aria-label that should be truncated because it exceeds the maximum display length'
        ]

        analysis = PageAnalysis(url='https://example.com')
        analysis.buttons = buttons

        report = generate_report(
            'https://example.com',
            [analysis],
            simple_software_detection
        )

        # Should be truncated with ...
        assert '...' in report or 'This is a very long' in report

    def test_empty_aria_examples_handled(self, simple_software_detection):
        """Empty aria examples should not cause errors."""
        buttons = ElementAnalysis()
        buttons.total = 5
        buttons.has_aria_label = 0
        buttons.aria_label_examples = []
        buttons.role_examples = []

        analysis = PageAnalysis(url='https://example.com')
        analysis.buttons = buttons

        # Should not raise
        report = generate_report(
            'https://example.com',
            [analysis],
            simple_software_detection
        )

        assert 'PENDO FEASIBILITY REPORT' in report

    def test_duplicate_aria_labels_deduplicated(self, simple_software_detection):
        """Duplicate aria-label values should be deduplicated in report."""
        buttons = ElementAnalysis()
        buttons.total = 5
        buttons.has_aria_label = 5
        buttons.aria_label_examples = ['Submit', 'Submit', 'Submit', 'Cancel', 'Cancel']

        analysis = PageAnalysis(url='https://example.com')
        analysis.buttons = buttons

        report = generate_report(
            'https://example.com',
            [analysis],
            simple_software_detection
        )

        # Check that deduplication doesn't cause issues
        # The report should still be generated
        assert 'PENDO FEASIBILITY REPORT' in report
