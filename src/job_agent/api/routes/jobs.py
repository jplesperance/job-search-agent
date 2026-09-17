from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from job_agent.api.dependencies import (
    get_job_ingestion_service,
    get_job_match_service,
    get_job_repository,
)
from job_agent.domain.jobs import (
    JobIngestRequest,
    JobIngestResponse,
    JobMatchRequest,
    JobMatchResponse,
    JobSummary,
    ParsedJobRequirement,
)
from job_agent.repositories.sqlalchemy import SqlAlchemyJobRepository
from job_agent.services.job_matching import JobIngestionService, JobMatchService

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("/ingest", response_model=JobIngestResponse)
def ingest_job(
    request: JobIngestRequest,
    service: JobIngestionService = Depends(get_job_ingestion_service),
) -> JobIngestResponse:
    return service.ingest(request)


@router.get("", response_model=list[JobSummary])
def list_jobs(
    limit: int = Query(default=100, ge=1, le=500),
    repo: SqlAlchemyJobRepository = Depends(get_job_repository),
) -> list[JobSummary]:
    jobs = repo.list(limit=limit)
    result: list[JobSummary] = []
    for job in jobs:
        result.append(
            JobSummary(
                id=job.id,
                source=job.source,
                external_id=job.external_id,
                source_url=str(job.source_url) if job.source_url else None,
                company=job.company,
                title=job.title,
                location=job.location,
                compensation_text=job.compensation_text,
                discovered_at=job.discovered_at,
                content_hash=job.content_hash,
            )
        )
    return result


@router.get("/{job_id}", response_model=JobSummary)
def get_job(
    job_id: UUID,
    repo: SqlAlchemyJobRepository = Depends(get_job_repository),
) -> JobSummary:
    job = repo.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobSummary(
        id=job.id,
        source=job.source,
        external_id=job.external_id,
        source_url=str(job.source_url) if job.source_url else None,
        company=job.company,
        title=job.title,
        location=job.location,
        compensation_text=job.compensation_text,
        discovered_at=job.discovered_at,
        content_hash=job.content_hash,
    )


@router.get("/{job_id}/requirements", response_model=list[ParsedJobRequirement])
def list_requirements(
    job_id: UUID,
    repo: SqlAlchemyJobRepository = Depends(get_job_repository),
) -> list[ParsedJobRequirement]:
    if repo.get(job_id) is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return repo.list_requirements(job_id)


@router.get("/{job_id}/analyses/latest", response_model=JobMatchResponse)
def latest_analysis(
    job_id: UUID,
    repo: SqlAlchemyJobRepository = Depends(get_job_repository),
) -> JobMatchResponse:
    if repo.get(job_id) is None:
        raise HTTPException(status_code=404, detail="Job not found")
    result = repo.latest_match_response(job_id)
    if result is None:
        raise HTTPException(status_code=404, detail="No analysis found for job")
    return result


@router.post("/{job_id}/analyze", response_model=JobMatchResponse)
def analyze_job(
    job_id: UUID,
    request: JobMatchRequest,
    service: JobMatchService = Depends(get_job_match_service),
) -> JobMatchResponse:
    try:
        return service.analyze(job_id, request)
    except LookupError as exc:
        message = str(exc)
        status = 404 if message == "job not found" else 409
        raise HTTPException(status_code=status, detail=message) from exc
