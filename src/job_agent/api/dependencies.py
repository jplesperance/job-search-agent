from fastapi import Depends
from sqlalchemy.orm import Session

from job_agent.db.session import get_db_session
from job_agent.repositories.sqlalchemy import SqlAlchemyCareerRepository, SqlAlchemyEvidenceRepository
from job_agent.services.evidence_search import EvidenceSearchService


def get_career_repository(
    session: Session = Depends(get_db_session),
) -> SqlAlchemyCareerRepository:
    return SqlAlchemyCareerRepository(session)


def get_evidence_repository(
    session: Session = Depends(get_db_session),
) -> SqlAlchemyEvidenceRepository:
    return SqlAlchemyEvidenceRepository(session)


def get_evidence_search_service(
    session: Session = Depends(get_db_session),
) -> EvidenceSearchService:
    career_repo = SqlAlchemyCareerRepository(session)
    evidence_repo = SqlAlchemyEvidenceRepository(session)
    return EvidenceSearchService(evidence_repo=evidence_repo, career_repo=career_repo)
