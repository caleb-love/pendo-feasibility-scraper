"""Background tasks for running scans."""

import json
from typing import Any

from server.storage import update_status, attach_results, REPORTS_DIR
from pendo_feasibility_scraper import run_scan, ScrapeConfig


def run_scan_task(scan_id: str, payload: dict[str, Any]) -> None:
    """Run a scan and persist results."""
    update_status(scan_id, 'running')
    try:
        config_payload = payload.get('config', {})
        config = ScrapeConfig(**config_payload)
        result = run_scan(payload['target_url'], config)
        
        REPORTS_DIR.mkdir(exist_ok=True)
        text_path = REPORTS_DIR / f'{scan_id}.txt'
        json_path = REPORTS_DIR / f'{scan_id}.json'
        
        text_path.write_text(result.report_text, encoding='utf-8')
        json_path.write_text(json.dumps(result.report_json, indent=2), encoding='utf-8')
        
        attach_results(scan_id, str(text_path), str(json_path))
        update_status(scan_id, 'finished')
    except Exception as exc:
        update_status(scan_id, 'failed', error_message=str(exc)[:200])
