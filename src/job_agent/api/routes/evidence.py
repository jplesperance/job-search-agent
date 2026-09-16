from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from job_agent.api.dependencies import get_evidence_repository, get_evidence_search_service
from job_agent.domain.retrieval import (
    EvidenceRecord,
    EvidenceSearchRequest,
    EvidenceSearchResponse,
    MatchMode,
    RetrievalScope,
)
from job_agent.repositories.sqlalchemy import SqlAlchemyEvidenceRepository
from job_agent.services.evidence_search import EvidenceSearchService

router = APIRouter(prefix="/evidence", tags=["evidence"])


@router.get("", response_model=EvidenceSearchResponse)
def search_evidence_get(
    skill: list[str] = Query(default=[]),
    q: str | None = Query(default=None, max_length=1000),
    scope: RetrievalScope = RetrievalScope.GENERAL,
    match_mode: MatchMode = MatchMode.ANY,
    limit: int = Query(default=20, ge=1, le=100),
    service: EvidenceSearchService = Depends(get_evidence_search_service),
) -> EvidenceSearchResponse:
    if not skill and not (q and q.strip()):
        raise HTTPException(status_code=422, detail="At least one skill or q parameter is required")

    request = EvidenceSearchRequest(
        query=q,
        skills=skill,
        scope=scope,
        match_mode=match_mode,
        limit=limit,
    )
    return service.search(request)


@router.post("/search", response_model=EvidenceSearchResponse)
def search_evidence_post(
    request: EvidenceSearchRequest,
    service: EvidenceSearchService = Depends(get_evidence_search_service),
) -> EvidenceSearchResponse:
    return service.search(request)


@router.get("/{identifier}", response_model=EvidenceRecord)
def get_evidence(
    identifier: str,
    repo: SqlAlchemyEvidenceRepository = Depends(get_evidence_repository),
) -> EvidenceRecord:
    lookup: UUID | str
    try:
        lookup = UUID(identifier)
    except ValueError:
        lookup = identifier

    record = repo.get(lookup)
    if record is None:
        raise HTTPException(status_code=404, detail="Evidence item not found")
    return record
