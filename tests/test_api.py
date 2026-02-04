"""Tests for FastAPI endpoints.

These tests require the full server dependencies to be installed.
If dependencies are missing, tests will be skipped.

Note: These tests are skipped by default due to complex dependency requirements
(cryptography, authlib, etc.). They can be run in environments where the full
server stack is installed.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Check if server dependencies are available at module level
# Must check authlib and cryptography which can cause runtime panics
def _check_server_available():
    try:
        import fastapi
        import starlette
        # Must also check authlib - it imports cryptography which can panic
        # in certain environments with broken Rust bindings
        import authlib
        return True
    except (ImportError, Exception):
        # Catch any exception including pyo3_runtime.PanicException
        return False

SERVER_DEPS_AVAILABLE = _check_server_available()

# Skip all tests in this module if basic FastAPI isn't available
pytestmark = pytest.mark.skipif(
    not SERVER_DEPS_AVAILABLE,
    reason="FastAPI dependencies not available"
)


@pytest.fixture
def mock_queue():
    """Mock the Redis queue."""
    mock = MagicMock()
    mock.enqueue = MagicMock(return_value=MagicMock(id='job-123'))
    return mock


@pytest.fixture
def app_client(mock_storage_paths, mock_queue):
    """Create a test client with mocked dependencies."""
    pytest.importorskip("fastapi")
    pytest.importorskip("authlib")

    from fastapi.testclient import TestClient

    with patch('server.storage.DATA_DIR', mock_storage_paths['data_dir']), \
         patch('server.storage.REPORTS_DIR', mock_storage_paths['reports_dir']), \
         patch('server.storage.DB_PATH', mock_storage_paths['db_path']), \
         patch('server.queue.get_queue', return_value=mock_queue):
        from server.app import app
        from server.storage import init_db
        init_db()
        with TestClient(app) as client:
            yield client


class TestHealthEndpoint:
    """Tests for /health endpoint."""

    def test_health_returns_ok(self, app_client):
        """Health endpoint should return ok status."""
        response = app_client.get('/health')

        assert response.status_code == 200
        assert response.json() == {'status': 'ok'}


class TestAuthEndpoints:
    """Tests for authentication endpoints."""

    def test_api_me_unauthenticated(self, app_client):
        """api/me should return empty dict when not authenticated."""
        response = app_client.get('/api/me')

        assert response.status_code == 200
        assert response.json() == {}

    def test_auth_logout_clears_session(self, app_client):
        """auth/logout should redirect to home."""
        response = app_client.get('/auth/logout', follow_redirects=False)

        assert response.status_code == 307  # Redirect
        assert response.headers['location'] == '/'


class TestScanEndpoints:
    """Tests for scan-related endpoints."""

    def test_create_scan_requires_auth(self, app_client):
        """POST /api/scans should require authentication."""
        response = app_client.post(
            '/api/scans',
            json={'target_url': 'https://example.com', 'config': {}}
        )

        assert response.status_code == 401

    def test_list_scans_requires_auth(self, app_client):
        """GET /api/scans should require authentication."""
        response = app_client.get('/api/scans')

        assert response.status_code == 401

    def test_get_scan_requires_auth(self, app_client):
        """GET /api/scans/{id} should require authentication."""
        response = app_client.get('/api/scans/some-scan-id')

        assert response.status_code == 401

    def test_get_scan_report_requires_auth(self, app_client):
        """GET /api/scans/{id}/report should require authentication."""
        response = app_client.get('/api/scans/some-scan-id/report')

        assert response.status_code == 401


class TestScanCreation:
    """Tests for scan creation with authentication."""

    @pytest.fixture
    def auth_client_with_mocks(self, mock_storage_paths, mock_queue):
        """Create authenticated client with all mocks."""
        pytest.importorskip("authlib")
        from fastapi.testclient import TestClient

        with patch('server.storage.DATA_DIR', mock_storage_paths['data_dir']), \
             patch('server.storage.REPORTS_DIR', mock_storage_paths['reports_dir']), \
             patch('server.storage.DB_PATH', mock_storage_paths['db_path']), \
             patch('server.queue.get_queue', return_value=mock_queue), \
             patch('server.app.get_current_user', return_value={'email': 'test@pendo.io'}):
            from server.app import app
            from server.storage import init_db
            init_db()
            with TestClient(app) as client:
                yield client, mock_queue

    def test_create_scan_valid_request(self, auth_client_with_mocks):
        """Valid scan request should succeed."""
        client, mock_queue = auth_client_with_mocks

        response = client.post(
            '/api/scans',
            json={
                'target_url': 'https://example.com',
                'config': {
                    'max_pages': 5,
                    'headless': True
                }
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert 'id' in data
        assert data['status'] == 'queued'
        mock_queue.enqueue.assert_called_once()

    def test_create_scan_enqueues_job(self, auth_client_with_mocks):
        """Scan creation should enqueue a background job."""
        client, mock_queue = auth_client_with_mocks

        client.post(
            '/api/scans',
            json={'target_url': 'https://example.com', 'config': {}}
        )

        mock_queue.enqueue.assert_called_once()
        call_args = mock_queue.enqueue.call_args
        assert call_args[0][0] == 'worker.tasks.run_scan_task'

    def test_create_scan_with_full_config(self, auth_client_with_mocks):
        """Scan with full configuration should be accepted."""
        client, mock_queue = auth_client_with_mocks

        response = client.post(
            '/api/scans',
            json={
                'target_url': 'https://example.com',
                'config': {
                    'max_links': 15,
                    'max_pages': 10,
                    'headless': False,
                    'include_query_params': True,
                    'allowlist_patterns': ['/app/', '/dashboard/'],
                    'denylist_patterns': ['/admin/'],
                    'login_mode': 'manual',
                    'dismiss_popups': True,
                    'scroll_pages': True
                }
            }
        )

        assert response.status_code == 200


class TestScanRetrieval:
    """Tests for retrieving scans."""

    @pytest.fixture
    def auth_client_with_scan(self, mock_storage_paths, mock_queue):
        """Create authenticated client with a pre-existing scan."""
        pytest.importorskip("authlib")
        from fastapi.testclient import TestClient

        with patch('server.storage.DATA_DIR', mock_storage_paths['data_dir']), \
             patch('server.storage.REPORTS_DIR', mock_storage_paths['reports_dir']), \
             patch('server.storage.DB_PATH', mock_storage_paths['db_path']), \
             patch('server.queue.get_queue', return_value=mock_queue), \
             patch('server.app.get_current_user', return_value={'email': 'test@pendo.io'}):
            from server.app import app
            from server.storage import init_db, create_scan

            init_db()
            scan_id = create_scan('https://example.com', {'max_pages': 5})

            with TestClient(app) as client:
                yield client, scan_id

    def test_list_scans_returns_list(self, auth_client_with_scan):
        """GET /api/scans should return a list."""
        client, scan_id = auth_client_with_scan

        response = client.get('/api/scans')

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]['id'] == scan_id

    def test_get_scan_returns_details(self, auth_client_with_scan):
        """GET /api/scans/{id} should return scan details."""
        client, scan_id = auth_client_with_scan

        response = client.get(f'/api/scans/{scan_id}')

        assert response.status_code == 200
        data = response.json()
        assert data['id'] == scan_id
        assert data['target_url'] == 'https://example.com'
        assert data['status'] == 'queued'

    def test_get_nonexistent_scan_returns_404(self, auth_client_with_scan):
        """GET /api/scans/{id} with bad ID should return 404."""
        client, _ = auth_client_with_scan

        response = client.get('/api/scans/nonexistent-id')

        assert response.status_code == 404


class TestScanReports:
    """Tests for scan report retrieval."""

    @pytest.fixture
    def auth_client_with_reports(self, mock_storage_paths, mock_queue):
        """Create authenticated client with scan that has reports."""
        pytest.importorskip("authlib")
        from fastapi.testclient import TestClient

        with patch('server.storage.DATA_DIR', mock_storage_paths['data_dir']), \
             patch('server.storage.REPORTS_DIR', mock_storage_paths['reports_dir']), \
             patch('server.storage.DB_PATH', mock_storage_paths['db_path']), \
             patch('server.queue.get_queue', return_value=mock_queue), \
             patch('server.app.get_current_user', return_value={'email': 'test@pendo.io'}):
            from server.app import app
            from server.storage import init_db, create_scan, attach_results, update_status

            init_db()
            scan_id = create_scan('https://example.com', {'max_pages': 5})

            # Create report files
            reports_dir = mock_storage_paths['reports_dir']
            text_path = reports_dir / f'{scan_id}.txt'
            json_path = reports_dir / f'{scan_id}.json'

            text_path.write_text('Test report content')
            json_path.write_text(json.dumps({'test': 'data'}))

            attach_results(scan_id, str(text_path), str(json_path))
            update_status(scan_id, 'finished')

            with TestClient(app) as client:
                yield client, scan_id

    def test_get_text_report(self, auth_client_with_reports):
        """GET /api/scans/{id}/report should return text report."""
        client, scan_id = auth_client_with_reports

        response = client.get(f'/api/scans/{scan_id}/report')

        assert response.status_code == 200
        assert response.text == 'Test report content'
        assert 'text/plain' in response.headers['content-type']

    def test_get_json_report(self, auth_client_with_reports):
        """GET /api/scans/{id}/report.json should return JSON report."""
        client, scan_id = auth_client_with_reports

        response = client.get(f'/api/scans/{scan_id}/report.json')

        assert response.status_code == 200
        assert response.json() == {'test': 'data'}
        assert 'application/json' in response.headers['content-type']

    def test_get_report_not_ready(self, mock_storage_paths, mock_queue):
        """Report endpoints should return 404 if report not ready."""
        pytest.importorskip("authlib")
        from fastapi.testclient import TestClient

        with patch('server.storage.DATA_DIR', mock_storage_paths['data_dir']), \
             patch('server.storage.REPORTS_DIR', mock_storage_paths['reports_dir']), \
             patch('server.storage.DB_PATH', mock_storage_paths['db_path']), \
             patch('server.queue.get_queue', return_value=mock_queue), \
             patch('server.app.get_current_user', return_value={'email': 'test@pendo.io'}):
            from server.app import app
            from server.storage import init_db, create_scan

            init_db()
            scan_id = create_scan('https://example.com', {})

            with TestClient(app) as client:
                response = client.get(f'/api/scans/{scan_id}/report')
                assert response.status_code == 404


class TestInputValidation:
    """Tests for API input validation."""

    @pytest.fixture
    def auth_client(self, mock_storage_paths, mock_queue):
        """Create authenticated client for validation tests."""
        pytest.importorskip("authlib")
        from fastapi.testclient import TestClient

        with patch('server.storage.DATA_DIR', mock_storage_paths['data_dir']), \
             patch('server.storage.REPORTS_DIR', mock_storage_paths['reports_dir']), \
             patch('server.storage.DB_PATH', mock_storage_paths['db_path']), \
             patch('server.queue.get_queue', return_value=mock_queue), \
             patch('server.app.get_current_user', return_value={'email': 'test@pendo.io'}):
            from server.app import app
            from server.storage import init_db
            init_db()
            with TestClient(app) as client:
                yield client

    def test_create_scan_missing_url(self, auth_client):
        """Create scan without URL should fail validation."""
        response = auth_client.post(
            '/api/scans',
            json={'config': {}}
        )

        assert response.status_code == 422  # Validation error

    def test_create_scan_invalid_json(self, auth_client):
        """Create scan with invalid JSON should fail."""
        response = auth_client.post(
            '/api/scans',
            content='not valid json',
            headers={'Content-Type': 'application/json'}
        )

        assert response.status_code == 422

    def test_create_scan_defaults_config(self, auth_client):
        """Create scan without config should use defaults."""
        response = auth_client.post(
            '/api/scans',
            json={'target_url': 'https://example.com'}
        )

        assert response.status_code == 200
