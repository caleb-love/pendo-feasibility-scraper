"""Tests for database storage operations."""

import json
import sqlite3
from pathlib import Path

import pytest

from server.storage import (
    init_db,
    create_scan,
    update_status,
    attach_results,
    get_scan,
    list_scans,
    get_connection,
)


class TestInitDb:
    """Tests for database initialization."""

    def test_init_db_creates_table(self, mock_storage_paths):
        """init_db should create the scans table."""
        init_db()

        # Verify table exists
        conn = get_connection()
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='scans'"
        )
        result = cursor.fetchone()
        conn.close()

        assert result is not None
        assert result['name'] == 'scans'

    def test_init_db_creates_correct_schema(self, mock_storage_paths):
        """init_db should create table with all required columns."""
        init_db()

        conn = get_connection()
        cursor = conn.execute("PRAGMA table_info(scans)")
        columns = {row['name']: row for row in cursor.fetchall()}
        conn.close()

        expected_columns = [
            'id', 'created_at', 'status', 'target_url', 'config_json',
            'report_text_path', 'report_json_path', 'error_message'
        ]

        for col_name in expected_columns:
            assert col_name in columns, f'Column {col_name} missing from schema'

    def test_init_db_idempotent(self, mock_storage_paths):
        """init_db should be safe to call multiple times."""
        init_db()
        init_db()  # Should not raise

        conn = get_connection()
        cursor = conn.execute(
            "SELECT COUNT(*) as count FROM sqlite_master WHERE type='table' AND name='scans'"
        )
        result = cursor.fetchone()
        conn.close()

        assert result['count'] == 1


class TestCreateScan:
    """Tests for scan creation."""

    def test_create_scan_returns_id(self, initialized_db, sample_scan_config):
        """create_scan should return a valid UUID."""
        scan_id = create_scan('https://example.com', sample_scan_config)

        assert scan_id is not None
        assert len(scan_id) == 36  # UUID format

    def test_create_scan_stores_data(self, initialized_db, sample_scan_config):
        """create_scan should store all provided data."""
        url = 'https://test.example.com'
        scan_id = create_scan(url, sample_scan_config)

        scan = get_scan(scan_id)

        assert scan is not None
        assert scan['target_url'] == url
        assert scan['status'] == 'queued'
        assert json.loads(scan['config_json']) == sample_scan_config
        assert scan['created_at'] is not None
        assert scan['created_at'].endswith('Z')

    def test_create_scan_unique_ids(self, initialized_db, sample_scan_config):
        """Each scan should get a unique ID."""
        ids = set()
        for _ in range(10):
            scan_id = create_scan('https://example.com', sample_scan_config)
            ids.add(scan_id)

        assert len(ids) == 10


class TestUpdateStatus:
    """Tests for status updates."""

    def test_update_status_changes_status(self, initialized_db, sample_scan_config):
        """update_status should change the scan status."""
        scan_id = create_scan('https://example.com', sample_scan_config)

        update_status(scan_id, 'running')

        scan = get_scan(scan_id)
        assert scan['status'] == 'running'

    def test_update_status_with_error(self, initialized_db, sample_scan_config):
        """update_status should store error messages."""
        scan_id = create_scan('https://example.com', sample_scan_config)
        error_msg = 'Connection timeout'

        update_status(scan_id, 'failed', error_message=error_msg)

        scan = get_scan(scan_id)
        assert scan['status'] == 'failed'
        assert scan['error_message'] == error_msg

    def test_update_status_transitions(self, initialized_db, sample_scan_config):
        """update_status should handle multiple transitions."""
        scan_id = create_scan('https://example.com', sample_scan_config)

        # Simulate state machine: queued -> running -> finished
        assert get_scan(scan_id)['status'] == 'queued'

        update_status(scan_id, 'running')
        assert get_scan(scan_id)['status'] == 'running'

        update_status(scan_id, 'finished')
        assert get_scan(scan_id)['status'] == 'finished'


class TestAttachResults:
    """Tests for attaching report paths."""

    def test_attach_results_stores_paths(self, initialized_db, sample_scan_config):
        """attach_results should store both report paths."""
        scan_id = create_scan('https://example.com', sample_scan_config)
        text_path = '/data/reports/123.txt'
        json_path = '/data/reports/123.json'

        attach_results(scan_id, text_path, json_path)

        scan = get_scan(scan_id)
        assert scan['report_text_path'] == text_path
        assert scan['report_json_path'] == json_path


class TestGetScan:
    """Tests for fetching scans."""

    def test_get_scan_existing(self, initialized_db, sample_scan_config):
        """get_scan should return scan data for valid ID."""
        scan_id = create_scan('https://example.com', sample_scan_config)

        scan = get_scan(scan_id)

        assert scan is not None
        assert scan['id'] == scan_id

    def test_get_scan_nonexistent(self, initialized_db):
        """get_scan should return None for invalid ID."""
        scan = get_scan('nonexistent-id')
        assert scan is None

    def test_get_scan_returns_dict(self, initialized_db, sample_scan_config):
        """get_scan should return a dictionary, not a Row object."""
        scan_id = create_scan('https://example.com', sample_scan_config)

        scan = get_scan(scan_id)

        assert isinstance(scan, dict)


class TestListScans:
    """Tests for listing scans."""

    def test_list_scans_empty(self, initialized_db):
        """list_scans should return empty list when no scans exist."""
        scans = list_scans()
        assert scans == []

    def test_list_scans_returns_all(self, initialized_db, sample_scan_config):
        """list_scans should return all scans."""
        urls = [f'https://example{i}.com' for i in range(5)]
        for url in urls:
            create_scan(url, sample_scan_config)

        scans = list_scans()

        assert len(scans) == 5

    def test_list_scans_order_by_created_at_desc(self, initialized_db, sample_scan_config):
        """list_scans should return scans newest first."""
        import time

        ids = []
        for i in range(3):
            scan_id = create_scan(f'https://example{i}.com', sample_scan_config)
            ids.append(scan_id)
            time.sleep(0.01)  # Small delay to ensure different timestamps

        scans = list_scans()

        # Newest first means last created should be first
        assert scans[0]['id'] == ids[2]
        assert scans[2]['id'] == ids[0]

    def test_list_scans_respects_limit(self, initialized_db, sample_scan_config):
        """list_scans should respect the limit parameter."""
        for i in range(10):
            create_scan(f'https://example{i}.com', sample_scan_config)

        scans = list_scans(limit=5)

        assert len(scans) == 5

    def test_list_scans_returns_dicts(self, initialized_db, sample_scan_config):
        """list_scans should return list of dictionaries."""
        create_scan('https://example.com', sample_scan_config)

        scans = list_scans()

        assert all(isinstance(s, dict) for s in scans)


class TestDataIntegrity:
    """Tests for data integrity and edge cases."""

    def test_special_characters_in_url(self, initialized_db, sample_scan_config):
        """URLs with special characters should be stored correctly."""
        url = 'https://example.com/path?query=value&special=!@#$%'
        scan_id = create_scan(url, sample_scan_config)

        scan = get_scan(scan_id)
        assert scan['target_url'] == url

    def test_unicode_in_error_message(self, initialized_db, sample_scan_config):
        """Unicode characters in error messages should be stored correctly."""
        scan_id = create_scan('https://example.com', sample_scan_config)
        error_msg = 'Error: 日本語メッセージ'

        update_status(scan_id, 'failed', error_message=error_msg)

        scan = get_scan(scan_id)
        assert scan['error_message'] == error_msg

    def test_complex_config_json(self, initialized_db):
        """Complex config dictionaries should be serialized correctly."""
        complex_config = {
            'nested': {'key': 'value', 'list': [1, 2, 3]},
            'bool': True,
            'null': None,
            'number': 42.5
        }

        scan_id = create_scan('https://example.com', complex_config)
        scan = get_scan(scan_id)

        assert json.loads(scan['config_json']) == complex_config
