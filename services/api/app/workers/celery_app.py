import os

from celery import Celery
from celery.schedules import crontab

broker = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
backend = os.environ.get("CELERY_RESULT_BACKEND", broker)

celery_app = Celery(
    "esn_wifi",
    broker=broker,
    backend=backend,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "poll-routers": {
            "task": "esn.routers.sync_all",
            "schedule": crontab(minute="*/5"),
        },
        "expire-sessions": {
            "task": "esn.sessions.expire_stale",
            "schedule": crontab(minute="*/2"),
        },
        "expire-vouchers": {
            "task": "esn.vouchers.mark_expired",
            "schedule": crontab(minute="*/10"),
        },
        "ingest-hotspot-sessions": {
            "task": "esn.routers.ingest_hotspot_sessions",
            "schedule": crontab(minute="*/3"),
        },
        "mark-router-offline-stale": {
            "task": "esn.routers.mark_offline_stale",
            "schedule": crontab(minute="*/2"),
        },
        "reconciliation-pass": {
            "task": "esn.reconciliation.run_once",
            "schedule": crontab(minute="*/15"),
        },
        "reconcile-hotspot-authorizations": {
            "task": "esn.routers.reconcile_hotspot_authorizations",
            "schedule": crontab(minute="*/2"),
        },
    },
)

# Import task modules so decorators register (after celery_app exists).
from app.workers.tasks import ping as _ping  # noqa: E402,F401
from app.workers.tasks import routers_sync as _routers_sync  # noqa: E402,F401
from app.workers.tasks import sessions as _sessions  # noqa: E402,F401
from app.workers.tasks import hotspot_ingest as _hotspot_ingest  # noqa: E402,F401
from app.workers.tasks import hotspot_authorization as _hotspot_authorization  # noqa: E402,F401
from app.workers.tasks import router_offline as _router_offline  # noqa: E402,F401
from app.workers.tasks import reconciliation as _reconciliation  # noqa: E402,F401
