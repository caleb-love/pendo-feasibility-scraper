"""Tests for software detection signatures.

The actual detect_software function requires a live Playwright page,
so these tests focus on the signature definitions and structure.
"""

import pytest
from pendo_feasibility_scraper import SOFTWARE_SIGNATURES, SoftwareDetection


class TestSoftwareSignatureStructure:
    """Tests for the structure of software signatures."""

    def test_has_all_categories(self):
        """SOFTWARE_SIGNATURES should have all expected categories."""
        expected_categories = ['frontend_frameworks', 'css_frameworks', 'analytics', 'other']

        for category in expected_categories:
            assert category in SOFTWARE_SIGNATURES, f'Missing category: {category}'

    def test_signatures_are_tuples(self):
        """Each signature should be a tuple of (check, name)."""
        for category, signatures in SOFTWARE_SIGNATURES.items():
            for sig in signatures:
                assert isinstance(sig, tuple), f'Signature in {category} is not a tuple'
                assert len(sig) == 2, f'Signature in {category} should have 2 elements'
                check, name = sig
                assert isinstance(check, str), f'Check in {category} should be string'
                assert isinstance(name, str), f'Name in {category} should be string'

    def test_checks_are_valid_js(self):
        """Each check should look like valid JavaScript."""
        for category, signatures in SOFTWARE_SIGNATURES.items():
            for check, name in signatures:
                # Should reference window or document
                assert 'window.' in check or 'document.' in check, \
                    f'Check for {name} should reference window or document'


class TestFrontendFrameworkSignatures:
    """Tests for frontend framework detection signatures."""

    def test_expected_frameworks_present(self):
        """All expected frontend frameworks should have signatures."""
        signatures = SOFTWARE_SIGNATURES['frontend_frameworks']
        framework_names = [name for _, name in signatures]

        expected = ['Next.js', 'Nuxt.js', 'AngularJS', 'Angular', 'Gatsby', 'Ember.js', 'Vue.js', 'React']

        for framework in expected:
            assert framework in framework_names, f'Missing signature for {framework}'

    def test_react_detection_methods(self):
        """React should be detectable via data-reactroot."""
        signatures = SOFTWARE_SIGNATURES['frontend_frameworks']

        react_sigs = [check for check, name in signatures if name == 'React']
        assert len(react_sigs) >= 1

        # Should look for data-reactroot
        assert any('reactroot' in check.lower() for check in react_sigs)

    def test_nextjs_detection_methods(self):
        """Next.js should have multiple detection methods."""
        signatures = SOFTWARE_SIGNATURES['frontend_frameworks']

        nextjs_sigs = [(check, name) for check, name in signatures if name == 'Next.js']
        assert len(nextjs_sigs) >= 1

        # Should check for __NEXT_DATA__ or __next element
        checks = [check for check, _ in nextjs_sigs]
        assert any('__NEXT' in check or '__next' in check for check in checks)


class TestCssFrameworkSignatures:
    """Tests for CSS framework detection signatures."""

    def test_expected_css_frameworks_present(self):
        """All expected CSS frameworks should have signatures."""
        signatures = SOFTWARE_SIGNATURES['css_frameworks']
        framework_names = [name for _, name in signatures]

        expected = ['Chakra UI', 'Mantine', 'Ant Design', 'Material UI', 'Blueprint']

        for framework in expected:
            assert framework in framework_names, f'Missing signature for {framework}'

    def test_frameworks_use_class_prefix_detection(self):
        """CSS frameworks should be detected by class prefixes."""
        signatures = SOFTWARE_SIGNATURES['css_frameworks']

        for check, name in signatures:
            # Should use querySelector with class selector
            assert 'querySelector' in check, f'{name} should use querySelector'
            assert '.' in check, f'{name} should check for class'


class TestAnalyticsSignatures:
    """Tests for analytics tool detection signatures."""

    def test_expected_analytics_present(self):
        """All expected analytics tools should have signatures."""
        signatures = SOFTWARE_SIGNATURES['analytics']
        tool_names = [name for _, name in signatures]

        expected = [
            'Pendo (already installed)', 'Segment', 'Mixpanel', 'Amplitude',
            'Heap', 'FullStory', 'Hotjar', 'Google Tag Manager', 'Intercom'
        ]

        for tool in expected:
            assert tool in tool_names, f'Missing signature for {tool}'

    def test_pendo_detection(self):
        """Pendo should be detectable."""
        signatures = SOFTWARE_SIGNATURES['analytics']

        pendo_sigs = [check for check, name in signatures if 'Pendo' in name]
        assert len(pendo_sigs) >= 1
        assert any('pendo' in check.lower() for check in pendo_sigs)

    def test_pendo_competitors_present(self):
        """Pendo competitors should be detectable."""
        signatures = SOFTWARE_SIGNATURES['analytics']
        tool_names = [name for _, name in signatures]

        competitors = ['Appcues', 'WalkMe', 'Userpilot', 'Chameleon']
        for competitor in competitors:
            assert competitor in tool_names, f'Missing Pendo competitor: {competitor}'


class TestOtherToolSignatures:
    """Tests for other tool detection signatures."""

    def test_expected_other_tools_present(self):
        """Expected other tools should have signatures."""
        signatures = SOFTWARE_SIGNATURES['other']
        tool_names = [name for _, name in signatures]

        expected = ['Sentry', 'Datadog RUM', 'LaunchDarkly', 'Stripe']

        for tool in expected:
            assert tool in tool_names, f'Missing signature for {tool}'


class TestSoftwareDetectionDataClass:
    """Tests for SoftwareDetection dataclass."""

    def test_empty_detection(self):
        """Empty SoftwareDetection should have empty lists."""
        detection = SoftwareDetection()

        assert detection.frontend_frameworks == []
        assert detection.css_frameworks == []
        assert detection.analytics_tools == []
        assert detection.other_tools == []
        assert detection.meta_generator == ''

    def test_populated_detection(self):
        """SoftwareDetection should store all categories."""
        detection = SoftwareDetection()
        detection.frontend_frameworks = ['React', 'Next.js']
        detection.css_frameworks = ['Material UI']
        detection.analytics_tools = ['Pendo (already installed)', 'Segment']
        detection.other_tools = ['Sentry']
        detection.meta_generator = 'WordPress 6.0'

        assert len(detection.frontend_frameworks) == 2
        assert len(detection.css_frameworks) == 1
        assert len(detection.analytics_tools) == 2
        assert len(detection.other_tools) == 1
        assert detection.meta_generator == 'WordPress 6.0'

    def test_detection_to_dict(self):
        """SoftwareDetection should be convertible to dict."""
        detection = SoftwareDetection()
        detection.frontend_frameworks = ['React']
        detection.analytics_tools = ['Pendo (already installed)']

        # __dict__ should work for serialization
        data = detection.__dict__

        assert data['frontend_frameworks'] == ['React']
        assert data['analytics_tools'] == ['Pendo (already installed)']


class TestSignatureCount:
    """Tests to ensure we have adequate coverage."""

    def test_minimum_frontend_signatures(self):
        """Should have at least 8 frontend framework signatures."""
        signatures = SOFTWARE_SIGNATURES['frontend_frameworks']
        assert len(signatures) >= 8

    def test_minimum_css_signatures(self):
        """Should have at least 5 CSS framework signatures."""
        signatures = SOFTWARE_SIGNATURES['css_frameworks']
        assert len(signatures) >= 5

    def test_minimum_analytics_signatures(self):
        """Should have at least 10 analytics tool signatures."""
        signatures = SOFTWARE_SIGNATURES['analytics']
        assert len(signatures) >= 10

    def test_total_signature_count(self):
        """Should have a reasonable total number of signatures."""
        total = sum(len(sigs) for sigs in SOFTWARE_SIGNATURES.values())
        assert total >= 25, f'Only {total} signatures defined, expected at least 25'
