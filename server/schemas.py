"""Pydantic schemas for API."""

from pydantic import BaseModel, Field


class ScanConfig(BaseModel):
    """Config passed to the scraper."""
    max_links: int = 20
    max_pages: int = 12
    headless: bool = True
    include_query_params: bool = False
    allowlist_patterns: list[str] = Field(default_factory=list)
    denylist_patterns: list[str] = Field(default_factory=list)
    login_mode: str = 'manual'
    login_url: str = ''
    username_selector: str = ''
    password_selector: str = ''
    submit_selector: str = ''
    username: str = ''
    password: str = ''
    storage_state_path: str = ''
    dismiss_popups: bool = True
    scroll_pages: bool = True


class ScanRequest(BaseModel):
    """Scan request payload."""
    target_url: str
    config: ScanConfig = ScanConfig()
