"""SQLite storage for scan metadata and results."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from uuid import uuid4


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / 'data'
REPORTS_DIR = DATA_DIR / 'reports'
DB_PATH = DATA_DIR / 'feasibility.db'


def ensure_dirs() -> None:
    """Ensure data directories exist."""
    DATA_DIR.mkdir(exist_ok=True)
    REPORTS_DIR.mkdir(exist_ok=True)


def get_connection() -> sqlite3.Connection:
    """Get a DB connection."""
    ensure_dirs()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Initialize DB schema."""
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS scans (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL,
                target_url TEXT NOT NULL,
                config_json TEXT NOT NULL,
                report_text_path TEXT,
                report_json_path TEXT,
                error_message TEXT
            )
            """
        )
        conn.commit()


def create_scan(target_url: str, config: dict) -> str:
    """Insert a new scan and return its ID."""
    scan_id = str(uuid4())
    created_at = datetime.utcnow().isoformat() + 'Z'
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO scans (id, created_at, status, target_url, config_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (scan_id, created_at, 'queued', target_url, json.dumps(config))
        )
        conn.commit()
    return scan_id


def update_status(scan_id: str, status: str, error_message: str = '') -> None:
    """Update scan status."""
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE scans
            SET status = ?, error_message = ?
            WHERE id = ?
            """,
            (status, error_message, scan_id)
        )
        conn.commit()


def attach_results(scan_id: str, report_text_path: str, report_json_path: str) -> None:
    """Attach report file paths."""
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE scans
            SET report_text_path = ?, report_json_path = ?
            WHERE id = ?
            """,
            (report_text_path, report_json_path, scan_id)
        )
        conn.commit()


def get_scan(scan_id: str) -> dict | None:
    """Fetch scan by ID."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM scans WHERE id = ?",
            (scan_id,)
        ).fetchone()
        if not row:
            return None
        return dict(row)


def list_scans(limit: int = 50) -> list:
    """List recent scans."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM scans ORDER BY created_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
