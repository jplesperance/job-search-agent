from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from job_agent.config.settings import get_settings


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    return create_engine(settings.database_url, pool_pre_ping=True)


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), class_=Session, expire_on_commit=False)


def get_db_session() -> Iterator[Session]:
    """Request-scoped unit of work.

    Read-only Phase 2 routes did not need transaction finalization. Phase 3 adds
    policy, job-ingestion, requirement, and analysis writes, so successful
    requests commit and failed requests roll back at the dependency boundary.
    """
    with get_session_factory()() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
