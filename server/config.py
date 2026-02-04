"""Configuration for the API server."""

import os
from dataclasses import dataclass


@dataclass
class Settings:
    """Environment-backed settings."""
    google_client_id: str = os.getenv('GOOGLE_OAUTH_CLIENT_ID', '')
    google_client_secret: str = os.getenv('GOOGLE_OAUTH_CLIENT_SECRET', '')
    google_redirect_uri: str = os.getenv('GOOGLE_OAUTH_REDIRECT_URI', '')
    allowed_google_domain: str = os.getenv('ALLOWED_GOOGLE_DOMAIN', 'pendo.io')
    session_secret: str = os.getenv('SESSION_SECRET', 'change-me')
    redis_url: str = os.getenv('REDIS_URL', 'redis://localhost:6379/0')


settings = Settings()
