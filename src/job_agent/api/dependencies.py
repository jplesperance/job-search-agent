from fastapi import Depends
from sqlalchemy.orm import Session

from job_agent.db.session import get_db_session
from job_agent.repositories.sqlalchemy import (
    SqlAlchemyCareerRepository,
    SqlAlchemyDiscoveryRepository,
    SqlAlchemyEvidenceRepository,
    SqlAlchemyJobRepository,
    SqlAlchemyPolicyRepository,
)
from job_agent.services.discovery import DiscoveryService
from job_agent.services.discovery_adapters import AdapterRegistry
from job_agent.services.evidence_search import EvidenceSearchService
from job_agent.services.job_matching import JobIngestionService, JobMatchService


def get_career_repository(
    session: Session = Depends(get_db_session),
) -> SqlAlchemyCareerRepository:
    return SqlAlchemyCareerRepository(session)


def get_evidence_repository(
    session: Session = Depends(get_db_session),
) -> SqlAlchemyEvidenceRepository:
    return SqlAlchemyEvidenceRepository(session)


def get_job_repository(
    session: Session = Depends(get_db_session),
) -> SqlAlchemyJobRepository:
    return SqlAlchemyJobRepository(session)


def get_policy_repository(
    session: Session = Depends(get_db_session),
) -> SqlAlchemyPolicyRepository:
    return SqlAlchemyPolicyRepository(session)


def get_evidence_search_service(
    session: Session = Depends(get_db_session),
) -> EvidenceSearchService:
    career_repo = SqlAlchemyCareerRepository(session)
    evidence_repo = SqlAlchemyEvidenceRepository(session)
    return EvidenceSearchService(evidence_repo=evidence_repo, career_repo=career_repo)


def get_job_ingestion_service(
    session: Session = Depends(get_db_session),
) -> JobIngestionService:
    return JobIngestionService(
        job_repo=SqlAlchemyJobRepository(session),
        career_repo=SqlAlchemyCareerRepository(session),
    )


def get_job_match_service(
    session: Session = Depends(get_db_session),
) -> JobMatchService:
    career_repo = SqlAlchemyCareerRepository(session)
    evidence_repo = SqlAlchemyEvidenceRepository(session)
    return JobMatchService(
        job_repo=SqlAlchemyJobRepository(session),
        policy_repo=SqlAlchemyPolicyRepository(session),
        career_repo=career_repo,
        evidence_search=EvidenceSearchService(evidence_repo=evidence_repo, career_repo=career_repo),
    )


def get_discovery_repository(
    session: Session = Depends(get_db_session),
) -> SqlAlchemyDiscoveryRepository:
    return SqlAlchemyDiscoveryRepository(session)


def get_discovery_service(
    session: Session = Depends(get_db_session),
) -> DiscoveryService:
    career_repo = SqlAlchemyCareerRepository(session)
    evidence_repo = SqlAlchemyEvidenceRepository(session)
    job_repo = SqlAlchemyJobRepository(session)
    policy_repo = SqlAlchemyPolicyRepository(session)
    ingestion = JobIngestionService(job_repo=job_repo, career_repo=career_repo)
    matcher = JobMatchService(
        job_repo=job_repo,
        policy_repo=policy_repo,
        career_repo=career_repo,
        evidence_search=EvidenceSearchService(evidence_repo=evidence_repo, career_repo=career_repo),
    )
    return DiscoveryService(
        discovery_repo=SqlAlchemyDiscoveryRepository(session),
        policy_repo=policy_repo,
        ingestion_service=ingestion,
        match_service=matcher,
        adapters=AdapterRegistry(),
    )
