from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from job_agent.config.settings import get_settings

settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


def get_db_session() -> Session:
    return SessionLocal()
