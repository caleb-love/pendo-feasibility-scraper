"""Shared test fixtures and configuration."""

import os
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# Skip test_api.py if cryptography/authlib have issues
# This is a collection-time check that prevents import errors
def _check_server_deps():
    """Check if server dependencies (authlib/cryptography) work."""
    try:
        # Test imports that are known to fail with broken Rust bindings
        from authlib.jose import JsonWebKey
        return True
    except BaseException:
        # Must catch BaseException because pyo3_runtime.PanicException
        # inherits from BaseException, not Exception
        return False


# Exclude test_api.py from collection if server deps are broken
collect_ignore = []
if not _check_server_deps():
    collect_ignore.append("test_api.py")


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)

    yield db_path

    # Cleanup
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def temp_data_dir(tmp_path):
    """Create a temporary data directory structure."""
    data_dir = tmp_path / 'data'
    reports_dir = data_dir / 'reports'
    data_dir.mkdir()
    reports_dir.mkdir()
    return {
        'data_dir': data_dir,
        'reports_dir': reports_dir,
        'db_path': data_dir / 'feasibility.db'
    }


@pytest.fixture
def mock_storage_paths(temp_data_dir, monkeypatch):
    """Patch storage module paths to use temp directories."""
    monkeypatch.setattr('server.storage.DATA_DIR', temp_data_dir['data_dir'])
    monkeypatch.setattr('server.storage.REPORTS_DIR', temp_data_dir['reports_dir'])
    monkeypatch.setattr('server.storage.DB_PATH', temp_data_dir['db_path'])
    return temp_data_dir


@pytest.fixture
def initialized_db(mock_storage_paths):
    """Initialize a test database with schema."""
    from server.storage import init_db
    init_db()
    return mock_storage_paths


@pytest.fixture
def sample_scan_config():
    """Return a sample scan configuration dict."""
    return {
        'max_links': 10,
        'max_pages': 5,
        'headless': True,
        'include_query_params': False,
        'allowlist_patterns': [],
        'denylist_patterns': [],
        'login_mode': 'manual',
        'dismiss_popups': True,
        'scroll_pages': True
    }


@pytest.fixture
def mock_session():
    """Create a mock session object for API testing."""
    session_data = {}

    class MockSession:
        def get(self, key, default=None):
            return session_data.get(key, default)

        def __setitem__(self, key, value):
            session_data[key] = value

        def __getitem__(self, key):
            return session_data[key]

        def clear(self):
            session_data.clear()

    return MockSession()


@pytest.fixture
def authenticated_session(mock_session):
    """Return a session with a logged-in user."""
    mock_session['user'] = {
        'email': 'test@pendo.io',
        'name': 'Test User'
    }
    return mock_session


@pytest.fixture
def sample_element_analysis():
    """Create a sample ElementAnalysis object."""
    from pendo_feasibility_scraper import ElementAnalysis
    analysis = ElementAnalysis()
    analysis.total = 10
    analysis.stable_ids = 5
    analysis.dynamic_ids = 2
    analysis.no_ids = 3
    analysis.has_pendo_attr = 1
    analysis.has_data_attr = 4
    analysis.has_text_content = 8
    # ARIA attributes
    analysis.has_aria_label = 3
    analysis.has_aria_describedby = 1
    analysis.has_role = 5
    analysis.has_title = 2
    analysis.aria_label_examples = ['Submit', 'Cancel']
    analysis.role_examples = ['button', 'link']
    return analysis


@pytest.fixture
def sample_page_analysis():
    """Create a sample PageAnalysis object."""
    from pendo_feasibility_scraper import PageAnalysis, ElementAnalysis

    buttons = ElementAnalysis()
    buttons.total = 5
    buttons.stable_ids = 3
    buttons.dynamic_ids = 1
    buttons.no_ids = 1

    inputs = ElementAnalysis()
    inputs.total = 3
    inputs.stable_ids = 2
    inputs.dynamic_ids = 0
    inputs.no_ids = 1

    links = ElementAnalysis()
    links.total = 10
    links.stable_ids = 5

    analysis = PageAnalysis(url='https://example.com/page1')
    analysis.buttons = buttons
    analysis.inputs = inputs
    analysis.links = links
    analysis.dynamic_class_count = 5
    analysis.dynamic_class_examples = [('btn-abc123', 'Dynamic hash suffix')]

    return analysis


@pytest.fixture
def sample_software_detection():
    """Create a sample SoftwareDetection object."""
    from pendo_feasibility_scraper import SoftwareDetection
    detection = SoftwareDetection()
    detection.frontend_frameworks = ['React', 'Next.js']
    detection.css_frameworks = ['Material UI']
    detection.analytics_tools = ['Segment', 'Heap']
    return detection
