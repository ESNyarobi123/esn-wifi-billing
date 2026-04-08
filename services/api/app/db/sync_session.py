"""Synchronous DB session for Celery workers."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

_sync_engine = create_engine(
    settings.sync_database_url,
    pool_pre_ping=True,
)
SyncSessionLocal = sessionmaker(bind=_sync_engine, autocommit=False, autoflush=False, class_=Session)


@contextmanager
def sync_session_scope() -> Generator[Session, None, None]:
    session = SyncSessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
