"""Queue helpers for scan jobs."""

from redis import Redis
from rq import Queue
from .config import settings


def get_queue() -> Queue:
    """Get a Redis-backed queue."""
    redis = Redis.from_url(settings.redis_url)
    return Queue('default', connection=redis)
