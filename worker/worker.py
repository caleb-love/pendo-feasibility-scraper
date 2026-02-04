"""RQ worker for scan jobs."""

from redis import Redis
from rq import Worker, Queue, Connection
from server.config import settings


def main() -> None:
    """Start worker process."""
    redis = Redis.from_url(settings.redis_url)
    with Connection(redis):
        worker = Worker([Queue('default')])
        worker.work()


if __name__ == '__main__':
    main()
