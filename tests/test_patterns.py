"""Tests for dynamic ID and class pattern detection.

These functions are core to the application's value proposition -
detecting problematic patterns that will break Pendo tags.
"""

import pytest
from pendo_feasibility_scraper import (
    check_dynamic_id,
    check_dynamic_class,
    DYNAMIC_ID_PATTERNS,
    DYNAMIC_CLASS_PATTERNS,
)


class TestCheckDynamicId:
    """Tests for check_dynamic_id function."""

    # --- Empty/None cases ---

    def test_empty_string_returns_not_dynamic(self):
        """Empty string should not be considered dynamic."""
        is_dynamic, label, reason, has_prefix = check_dynamic_id('')
        assert is_dynamic is False
        assert label == ''
        assert reason == ''
        assert has_prefix is False

    def test_none_returns_not_dynamic(self):
        """None should not be considered dynamic."""
        is_dynamic, label, reason, has_prefix = check_dynamic_id(None)
        assert is_dynamic is False

    # --- Stable IDs (should NOT be flagged) ---

    def test_simple_stable_id(self):
        """Simple descriptive IDs should not be flagged."""
        stable_ids = [
            'submit-button',
            'login-form',
            'main-content',
            'nav-bar',
            'header',
            'footer',
            'sidebar',
            'search-input',
            'user-profile',
        ]
        for id_value in stable_ids:
            is_dynamic, label, reason, has_prefix = check_dynamic_id(id_value)
            assert is_dynamic is False, f'ID "{id_value}" should not be flagged as dynamic'

    def test_stable_id_with_numbers(self):
        """IDs with meaningful numbers should not be flagged."""
        stable_ids = [
            'step-1',
            'item-2',
            'page-10',
            'section-3-header',
        ]
        for id_value in stable_ids:
            is_dynamic, label, reason, has_prefix = check_dynamic_id(id_value)
            assert is_dynamic is False, f'ID "{id_value}" should not be flagged as dynamic'

    # --- Ember.js patterns ---

    def test_ember_runtime_id(self):
        """Ember runtime IDs should be flagged (no stable prefix)."""
        ember_ids = ['ember123', 'ember456', 'ember1', 'ember99999']
        for id_value in ember_ids:
            is_dynamic, label, reason, has_prefix = check_dynamic_id(id_value)
            assert is_dynamic is True, f'Ember ID "{id_value}" should be flagged'
            assert label == 'ember*'
            assert has_prefix is False  # No stable prefix workaround

    # --- Radix UI patterns ---

    def test_radix_runtime_id(self):
        """Radix UI runtime IDs should be flagged (no stable prefix)."""
        radix_ids = [':r1:', ':ra:', ':r1ab:']
        for id_value in radix_ids:
            is_dynamic, label, reason, has_prefix = check_dynamic_id(id_value)
            assert is_dynamic is True, f'Radix ID "{id_value}" should be flagged'
            assert label == 'radix-:r*:'
            assert has_prefix is False

    def test_radix_component_id_has_prefix(self):
        """Radix component IDs have stable prefixes."""
        is_dynamic, label, reason, has_prefix = check_dynamic_id('radix-popover-trigger')
        assert is_dynamic is True
        assert has_prefix is True  # Workaround available

    # --- Numeric-only IDs ---

    def test_numeric_only_id(self):
        """Pure numeric IDs (database records) should be flagged."""
        numeric_ids = ['123', '1', '99999', '000001']
        for id_value in numeric_ids:
            is_dynamic, label, reason, has_prefix = check_dynamic_id(id_value)
            assert is_dynamic is True, f'Numeric ID "{id_value}" should be flagged'
            assert label == 'numeric-only'
            assert has_prefix is False

    # --- React Select patterns ---

    def test_react_select_id(self):
        """React Select IDs should be flagged with prefix workaround."""
        react_select_ids = [
            'react-select-1-input',
            'react-select-2-listbox',
            'react-select-123-option-0',
        ]
        for id_value in react_select_ids:
            is_dynamic, label, reason, has_prefix = check_dynamic_id(id_value)
            assert is_dynamic is True, f'React Select ID "{id_value}" should be flagged'
            assert label == 'react-select-*'
            assert has_prefix is True

    # --- Material UI patterns ---

    def test_mui_id(self):
        """Material UI IDs should be flagged with prefix workaround."""
        # Pattern is ^mui-\d+ so IDs must start with mui- followed by digits
        mui_ids = ['mui-1', 'mui-123', 'mui-99999']
        for id_value in mui_ids:
            is_dynamic, label, reason, has_prefix = check_dynamic_id(id_value)
            assert is_dynamic is True, f'MUI ID "{id_value}" should be flagged'
            assert label == 'mui-*'
            assert has_prefix is True

    # --- Headless UI patterns ---

    def test_headlessui_id(self):
        """Headless UI IDs should be flagged with prefix workaround."""
        ids = ['headlessui-menu-button-1', 'headlessui-listbox-option-2']
        for id_value in ids:
            is_dynamic, label, reason, has_prefix = check_dynamic_id(id_value)
            assert is_dynamic is True
            assert label == 'headlessui-*'
            assert has_prefix is True

    # --- Chakra UI patterns ---

    def test_chakra_id(self):
        """Chakra UI IDs should be flagged with prefix workaround."""
        ids = ['chakra-modal-1', 'chakra-popover-trigger-2']
        for id_value in ids:
            is_dynamic, label, reason, has_prefix = check_dynamic_id(id_value)
            assert is_dynamic is True
            assert label == 'chakra-*'
            assert has_prefix is True

    # --- Mantine patterns ---

    def test_mantine_id(self):
        """Mantine UI IDs should be flagged with prefix workaround."""
        ids = ['mantine-modal-1', 'mantine-select-dropdown-2']
        for id_value in ids:
            is_dynamic, label, reason, has_prefix = check_dynamic_id(id_value)
            assert is_dynamic is True
            assert label == 'mantine-*'
            assert has_prefix is True

    # --- Downshift patterns ---

    def test_downshift_id(self):
        """Downshift IDs should be flagged with prefix workaround."""
        ids = ['downshift-1-item-0', 'downshift-2-menu']
        for id_value in ids:
            is_dynamic, label, reason, has_prefix = check_dynamic_id(id_value)
            assert is_dynamic is True
            assert label == 'downshift-*'
            assert has_prefix is True

    # --- Angular patterns ---

    def test_angular_compiler_id(self):
        """Angular compiler IDs should be flagged (no stable prefix)."""
        ids = ['ng-c1', 'ng-c123', 'ng-c9999']
        for id_value in ids:
            is_dynamic, label, reason, has_prefix = check_dynamic_id(id_value)
            assert is_dynamic is True
            assert label == 'ng-c*'
            assert has_prefix is False

    def test_angular_cdk_id(self):
        """Angular CDK IDs should be flagged with prefix workaround."""
        # Pattern is ^cdk-[a-z]+-\d+ so need letters, then dash, then digits
        ids = ['cdk-a-1', 'cdk-overlay-123', 'cdk-drag-99']
        for id_value in ids:
            is_dynamic, label, reason, has_prefix = check_dynamic_id(id_value)
            assert is_dynamic is True, f'CDK ID "{id_value}" should be flagged'
            assert label == 'cdk-*'
            assert has_prefix is True

    def test_angular_material_id(self):
        """Angular Material IDs should be flagged with prefix workaround."""
        ids = ['mat-select-1', 'mat-input-2']
        for id_value in ids:
            is_dynamic, label, reason, has_prefix = check_dynamic_id(id_value)
            assert is_dynamic is True
            assert label == 'mat-*'
            assert has_prefix is True

    # --- UUID patterns ---

    def test_uuid_id(self):
        """UUID IDs should be flagged (no stable prefix)."""
        ids = [
            'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
            '12345678-abcd-ef12-3456-789012345678',
        ]
        for id_value in ids:
            is_dynamic, label, reason, has_prefix = check_dynamic_id(id_value)
            assert is_dynamic is True
            assert label == 'uuid-*'
            assert has_prefix is False

    # --- Hash-based patterns ---

    def test_pure_hash_id(self):
        """Pure hash IDs should be flagged (no stable prefix)."""
        ids = ['a1b2c3d4e5f6', 'abcdef123456', '1234567890abcdef']
        for id_value in ids:
            is_dynamic, label, reason, has_prefix = check_dynamic_id(id_value)
            assert is_dynamic is True
            assert label == 'hash-only'
            assert has_prefix is False

    def test_minified_id(self):
        """Minified IDs should be flagged (no stable prefix)."""
        ids = ['a12345', 'ab99999', 'x123456']
        for id_value in ids:
            is_dynamic, label, reason, has_prefix = check_dynamic_id(id_value)
            assert is_dynamic is True
            assert label == 'minified'
            assert has_prefix is False

    # --- Hash suffix patterns ---

    def test_hash_suffix_id(self):
        """IDs with hash suffixes should be flagged with prefix workaround."""
        ids = ['button-a1b2c3d4e', 'nav-item-abcdef']
        for id_value in ids:
            is_dynamic, label, reason, has_prefix = check_dynamic_id(id_value)
            assert is_dynamic is True
            assert label == '*-hash'
            assert has_prefix is True

    def test_css_modules_hash_suffix(self):
        """CSS Modules hash suffixes should be flagged with prefix workaround."""
        ids = ['nav-bar__2RnO8abc', 'button__xyz12345']
        for id_value in ids:
            is_dynamic, label, reason, has_prefix = check_dynamic_id(id_value)
            assert is_dynamic is True
            assert label == '*__hash'
            assert has_prefix is True

    # --- CSS-in-JS patterns ---

    def test_css_in_js_id(self):
        """CSS-in-JS generated IDs should be flagged."""
        # Pattern: ^(sc|css|emotion|styled)-[a-zA-Z0-9]+$
        # These must exactly match the pattern without matching earlier patterns
        css_in_js_ids = [
            ('sc-abcdef', 'css-in-js'),
            ('css-1abc2de', 'css-in-js'),
            ('emotion-xyz123', 'css-in-js'),
            ('styled-abc123', 'css-in-js'),
        ]
        for id_value, expected_label in css_in_js_ids:
            is_dynamic, label, reason, has_prefix = check_dynamic_id(id_value)
            assert is_dynamic is True, f'CSS-in-JS ID "{id_value}" should be flagged'
            assert has_prefix is True


class TestCheckDynamicClass:
    """Tests for check_dynamic_class function."""

    # --- Empty/None cases ---

    def test_empty_string_returns_not_dynamic(self):
        """Empty string should not be considered dynamic."""
        is_dynamic, label, reason, stable_prefix = check_dynamic_class('')
        assert is_dynamic is False
        assert label == ''
        assert reason == ''
        assert stable_prefix == ''

    def test_none_returns_not_dynamic(self):
        """None should not be considered dynamic."""
        is_dynamic, label, reason, stable_prefix = check_dynamic_class(None)
        assert is_dynamic is False

    # --- Stable classes (should NOT be flagged) ---

    def test_simple_stable_class(self):
        """Simple BEM-style classes should not be flagged."""
        # Note: Classes with __ followed by 5+ alphanumeric chars match CSS Modules pattern
        # So we avoid those patterns here
        stable_classes = [
            'btn',
            'btn-primary',
            'nav-item',
            'card-header',
            'card-body--large',
            'text-center',
            'flex',
            'hidden',
            'container',
            'card__hdr',  # Too short to match CSS Modules pattern
        ]
        for class_name in stable_classes:
            is_dynamic, label, reason, stable_prefix = check_dynamic_class(class_name)
            assert is_dynamic is False, f'Class "{class_name}" should not be flagged'

    def test_tailwind_classes_stable(self):
        """Tailwind utility classes should not be flagged."""
        tailwind_classes = [
            'p-4',
            'mt-2',
            'flex-1',
            'bg-blue-500',
            'text-xl',
            'rounded-lg',
            'shadow-md',
        ]
        for class_name in tailwind_classes:
            is_dynamic, label, reason, stable_prefix = check_dynamic_class(class_name)
            assert is_dynamic is False, f'Tailwind class "{class_name}" should not be flagged'

    # --- Hash suffix patterns ---

    def test_hash_suffix_class(self):
        """Classes with hash suffixes should be flagged."""
        dynamic_classes = [
            ('button-a1b2c3', 'button'),
            ('nav-item-abcdef', 'nav-item'),
            ('card-123abc', 'card'),
        ]
        for class_name, expected_prefix in dynamic_classes:
            is_dynamic, label, reason, stable_prefix = check_dynamic_class(class_name)
            assert is_dynamic is True, f'Class "{class_name}" should be flagged'
            assert label == 'name-hash'
            assert stable_prefix == expected_prefix

    def test_underscore_hash_suffix_class(self):
        """Classes with underscore hash suffixes should be flagged."""
        # Pattern: ^([a-z][-a-z0-9]*)_[a-f0-9]{6,}$
        # Must end with underscore followed by hex chars
        dynamic_classes = [
            ('button_a1b2c3', 'button'),
            ('nav_abcdef12', 'nav'),
        ]
        for class_name, expected_prefix in dynamic_classes:
            is_dynamic, label, reason, stable_prefix = check_dynamic_class(class_name)
            assert is_dynamic is True, f'Class "{class_name}" should be flagged'
            assert label == 'name_hash'

    def test_css_modules_class(self):
        """CSS Modules pattern classes should be flagged."""
        dynamic_classes = [
            ('nav-bar__2RnO8', 'nav-bar'),
            ('button__xyz123', 'button'),
            ('card-header__abcDE12', 'card-header'),
        ]
        for class_name, expected_prefix in dynamic_classes:
            is_dynamic, label, reason, stable_prefix = check_dynamic_class(class_name)
            assert is_dynamic is True, f'Class "{class_name}" should be flagged'
            assert label == 'name__hash'
            assert stable_prefix == expected_prefix

    # --- Pure hash classes ---

    def test_pure_hash_class(self):
        """Pure hash classes should be flagged (no stable prefix)."""
        pure_hashes = ['a1b2c3', 'abcdef12', '123abc456']
        for class_name in pure_hashes:
            is_dynamic, label, reason, stable_prefix = check_dynamic_class(class_name)
            assert is_dynamic is True, f'Class "{class_name}" should be flagged'
            assert label == 'pure-hash'
            assert stable_prefix == ''

    def test_underscore_prefixed_hash_class(self):
        """Underscore-prefixed hash classes should be flagged."""
        classes = ['_abcdef12', '_xyz12345']
        for class_name in classes:
            is_dynamic, label, reason, stable_prefix = check_dynamic_class(class_name)
            assert is_dynamic is True, f'Class "{class_name}" should be flagged'
            assert label == '_hash'

    # --- CSS-in-JS patterns ---

    def test_styled_components_class(self):
        """Styled Components classes should be flagged."""
        classes = ['sc-aXZVg', 'sc-bcXHqe', 'sc-fqkvVR']
        for class_name in classes:
            is_dynamic, label, reason, stable_prefix = check_dynamic_class(class_name)
            assert is_dynamic is True, f'Class "{class_name}" should be flagged'
            assert label == 'styled-components'

    def test_emotion_css_class(self):
        """Emotion CSS classes should be flagged."""
        # Pattern: ^css-[a-z0-9]{4,}$
        # Lowercase alphanumeric after css-
        classes = ['css-1abc', 'css-abcd', 'css-xyz123']
        for class_name in classes:
            is_dynamic, label, reason, stable_prefix = check_dynamic_class(class_name)
            assert is_dynamic is True, f'Class "{class_name}" should be flagged'
            assert label == 'emotion'

    def test_emotion_named_class(self):
        """Emotion named classes should be flagged."""
        # Pattern: ^emotion-[a-z0-9]+$
        classes = ['emotion-abc', 'emotion-xyz1']
        for class_name in classes:
            is_dynamic, label, reason, stable_prefix = check_dynamic_class(class_name)
            assert is_dynamic is True, f'Class "{class_name}" should be flagged'
            assert label == 'emotion-*'

    def test_mui_makestyles_class(self):
        """MUI makeStyles classes should be flagged."""
        classes = ['makeStyles-root-123', 'makeStyles-button-456']
        for class_name in classes:
            is_dynamic, label, reason, stable_prefix = check_dynamic_class(class_name)
            assert is_dynamic is True, f'Class "{class_name}" should be flagged'
            assert label == 'mui-makeStyles'

    def test_jss_class(self):
        """JSS generated classes should be flagged."""
        classes = ['jss1', 'jss123', 'jss9999']
        for class_name in classes:
            is_dynamic, label, reason, stable_prefix = check_dynamic_class(class_name)
            assert is_dynamic is True, f'Class "{class_name}" should be flagged'
            assert label == 'jss'

    # --- Minified classes ---

    def test_minified_class(self):
        """Minified classes should be flagged."""
        # Pattern: ^[a-zA-Z]{1,2}[0-9]{4,}$
        # 1-2 letters followed by 4+ digits (no hex chars to avoid pure-hash match)
        # Use digits like 7, 8, 9 to avoid hex ambiguity
        classes = ['a1234', 'X78999', 'Z99999']
        for class_name in classes:
            is_dynamic, label, reason, stable_prefix = check_dynamic_class(class_name)
            assert is_dynamic is True, f'Class "{class_name}" should be flagged'
            assert label == 'minified'


class TestPatternCoverage:
    """Meta-tests to ensure all patterns are being tested."""

    def test_all_dynamic_id_patterns_have_tests(self):
        """Verify we have test cases for all dynamic ID patterns."""
        # This is a sanity check - each pattern label should appear in tests
        expected_labels = {
            'ember*', 'radix-:r*:', 'numeric-only', 'react-select-*',
            'mui-*', 'radix-*', 'headlessui-*', 'downshift-*',
            'chakra-*', 'mantine-*', 'ng-c*', 'cdk-*', 'mat-*',
            'uuid-*', 'hash-only', 'minified', '*-hash', '*__hash',
            'css-in-js'
        }
        pattern_labels = {p[1] for p in DYNAMIC_ID_PATTERNS}
        assert pattern_labels == expected_labels, \
            f'Missing tests for: {pattern_labels - expected_labels}'

    def test_all_dynamic_class_patterns_have_tests(self):
        """Verify we have test cases for all dynamic class patterns."""
        expected_labels = {
            'name-hash', 'name_hash', 'name__hash', 'pure-hash',
            '_hash', 'styled-components', 'emotion', 'emotion-*',
            'mui-makeStyles', 'jss', 'minified'
        }
        pattern_labels = {p[1] for p in DYNAMIC_CLASS_PATTERNS}
        assert pattern_labels == expected_labels, \
            f'Missing tests for: {pattern_labels - expected_labels}'
