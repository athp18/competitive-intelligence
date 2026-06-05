from celery import Celery
from celery.schedules import crontab

from core.config import get_settings

settings = get_settings()

app = Celery(
    "cie",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "tasks.crawl",
        "tasks.extract",
        "tasks.analyze",
        "tasks.alert",
    ],
)

app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "tasks.crawl.*": {"queue": "crawl"},
        "tasks.extract.*": {"queue": "llm"},
        "tasks.analyze.*": {"queue": "llm"},
        "tasks.alert.*": {"queue": "default"},
    },
    beat_schedule={
        "crawl-news-6h": {
            "task": "tasks.crawl.crawl_all",
            "schedule": crontab(minute=0, hour="*/6"),
            "args": ["news"],
        },
        "crawl-hn-6h": {
            "task": "tasks.crawl.crawl_all",
            "schedule": crontab(minute=30, hour="*/6"),
            "args": ["hn"],
        },
        "crawl-github-daily": {
            "task": "tasks.crawl.crawl_all",
            "schedule": crontab(hour=2, minute=0),
            "args": ["github"],
        },
        "crawl-arxiv-daily": {
            "task": "tasks.crawl.crawl_all",
            "schedule": crontab(hour=2, minute=15),
            "args": ["arxiv"],
        },
        "crawl-greenhouse-daily": {
            "task": "tasks.crawl.crawl_all",
            "schedule": crontab(hour=2, minute=30),
            "args": ["greenhouse"],
        },
        "crawl-lever-daily": {
            "task": "tasks.crawl.crawl_all",
            "schedule": crontab(hour=2, minute=45),
            "args": ["lever"],
        },
        "analysis-daily": {
            "task": "tasks.analyze.run_all_analysis",
            "schedule": crontab(hour=6, minute=0),
        },
    },
)
