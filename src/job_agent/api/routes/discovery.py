from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from job_agent.api.dependencies import get_discovery_repository, get_discovery_service
from job_agent.domain.discovery import (
    DiscoveryBatchResponse,
    DiscoveryCandidateSummary,
    DiscoveryRunRequest,
    DiscoveryRunSummary,
    DiscoverySourceCreate,
    DiscoverySourceSummary,
)
from job_agent.repositories.sqlalchemy import SqlAlchemyDiscoveryRepository
from job_agent.services.discovery import DiscoveryService

router = APIRouter(prefix="/discovery", tags=["discovery"])


@router.post("/sources", response_model=DiscoverySourceSummary)
def add_source(
    request: DiscoverySourceCreate,
    repo: SqlAlchemyDiscoveryRepository = Depends(get_discovery_repository),
) -> DiscoverySourceSummary:
    return repo.add_source(request)


@router.get("/sources", response_model=list[DiscoverySourceSummary])
def list_sources(
    enabled_only: bool = Query(default=False),
    repo: SqlAlchemyDiscoveryRepository = Depends(get_discovery_repository),
) -> list[DiscoverySourceSummary]:
    return repo.list_sources(enabled_only=enabled_only)


@router.post("/run", response_model=DiscoveryBatchResponse)
def run_discovery(
    request: DiscoveryRunRequest,
    service: DiscoveryService = Depends(get_discovery_service),
) -> DiscoveryBatchResponse:
    try:
        return service.run(request)
    except LookupError as exc:
        message = str(exc)
        status = 404 if "source" in message else 409
        raise HTTPException(status_code=status, detail=message) from exc


@router.get("/runs", response_model=list[DiscoveryRunSummary])
def list_runs(
    limit: int = Query(default=100, ge=1, le=500),
    repo: SqlAlchemyDiscoveryRepository = Depends(get_discovery_repository),
) -> list[DiscoveryRunSummary]:
    return repo.list_runs(limit=limit)


@router.get("/candidates", response_model=list[DiscoveryCandidateSummary])
def list_candidates(
    minimum_score: float = Query(default=80.0, ge=0, le=100),
    limit: int = Query(default=100, ge=1, le=500),
    open_only: bool = Query(default=True),
    repo: SqlAlchemyDiscoveryRepository = Depends(get_discovery_repository),
) -> list[DiscoveryCandidateSummary]:
    return repo.list_candidates(minimum_score=minimum_score, limit=limit, open_only=open_only)
