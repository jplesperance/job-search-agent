from __future__ import annotations

import re
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from job_agent.domain.enums import ApprovalStatus, ResumeVisibility, VerificationStatus
from job_agent.domain.models import EvidenceItem, Experience, Skill


class RetrievalScope(StrEnum):
    GENERAL = "general"
    MATCHING = "matching"
    RESUME = "resume"


class MatchMode(StrEnum):
    ANY = "any"
    ALL = "all"


class EvidenceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence: EvidenceItem
    experience: Experience | None = None
    skills: list[Skill] = Field(default_factory=list)


class EvidenceSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str | None = Field(default=None, max_length=1000)
    skills: list[str] = Field(default_factory=list, max_length=25)
    experience_ids: list[UUID] = Field(default_factory=list, max_length=50)
    categories: list[str] = Field(default_factory=list, max_length=50)
    scope: RetrievalScope = RetrievalScope.GENERAL
    match_mode: MatchMode = MatchMode.ANY
    verification_statuses: list[VerificationStatus] = Field(
        default_factory=lambda: [
            VerificationStatus.USER_VERIFIED,
            VerificationStatus.CORROBORATED,
            VerificationStatus.SOURCE_FACT,
        ]
    )
    approval_statuses: list[ApprovalStatus] = Field(
        default_factory=lambda: [ApprovalStatus.APPROVED]
    )
    resume_eligible: bool | None = None
    resume_visibility: list[ResumeVisibility] = Field(default_factory=list)
    limit: int = Field(default=20, ge=1, le=100)

    @model_validator(mode="after")
    def require_search_criteria(self) -> "EvidenceSearchRequest":
        if not (self.query and self.query.strip()) and not self.skills:
            raise ValueError("At least one of query or skills is required")
        return self


class EvidenceSearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: UUID
    evidence_key: str | None
    claim: str
    category: str
    context: str | None
    metric: str | None
    verification_status: VerificationStatus | None
    approval_status: ApprovalStatus
    resume_eligible: bool
    resume_visibility: ResumeVisibility | None
    safe_for_resume: bool
    tags: list[str]
    experience_id: UUID | None
    experience_key: str | None
    employer: str | None
    title: str | None
    matched_skills: list[str]
    all_skills: list[str]
    score: float = Field(ge=0, le=100)
    score_reasons: list[str] = Field(default_factory=list)


class EvidenceSearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str | None
    requested_skills: list[str]
    resolved_skills: dict[str, list[str]]
    unknown_skills: list[str]
    count: int
    results: list[EvidenceSearchResult]


def normalize_term(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.lower()))
