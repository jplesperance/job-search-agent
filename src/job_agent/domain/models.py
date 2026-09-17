from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from job_agent.domain.jobs import LocationCompensationRule

from job_agent.domain.enums import (
    ApplicationStatus,
    ApprovalStatus,
    ResumeVisibility,
    VerificationStatus,
)


class DomainModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class CareerProfile(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    display_name: str
    professional_headline: str | None = None
    summary: str | None = None


class Experience(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    canonical_key: str | None = None
    profile_id: UUID
    employer: str
    title: str
    start_date: date
    end_date: date | None = None
    location: str | None = None
    description: str | None = None
    verification_status: VerificationStatus | None = None


class EvidenceItem(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    evidence_key: str | None = None
    experience_id: UUID | None = None
    category: str
    claim: str
    context: str | None = None
    metric: str | None = None
    provenance: str | None = None
    verification_status: VerificationStatus | None = None
    approval_status: ApprovalStatus = ApprovalStatus.DRAFT
    resume_eligible: bool = False
    resume_visibility: ResumeVisibility | None = None
    tags: set[str] = Field(default_factory=set)


class Skill(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    category: str | None = None
    aliases: set[str] = Field(default_factory=set)


class Certification(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    profile_id: UUID
    name: str
    issuer: str
    issued_on: date | None = None
    expires_on: date | None = None
    credential_id: str | None = None
    approval_status: ApprovalStatus = ApprovalStatus.APPROVED


class TargetingPolicy(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    version: int = 1
    active: bool = False
    target_titles: list[str] = Field(default_factory=list)
    target_seniority: list[str] = Field(default_factory=list)
    allowed_locations: list[str] = Field(default_factory=list)
    remote_allowed: bool = True
    hybrid_allowed: bool = True
    onsite_allowed: bool = False
    minimum_base_salary_usd: Decimal | None = None
    remote_minimum_base_salary_usd: Decimal | None = None
    location_compensation_rules: list[LocationCompensationRule] = Field(default_factory=list)
    required_terms: set[str] = Field(default_factory=set)
    excluded_terms: set[str] = Field(default_factory=set)
    weights: dict[str, float] = Field(default_factory=dict)


class JobOpportunity(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    source: str
    external_id: str | None = None
    source_url: HttpUrl | None = None
    company: str
    title: str
    location: str | None = None
    compensation_text: str | None = None
    work_arrangement: str | None = None
    description_raw: str
    content_hash: str | None = None
    discovered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ScoreComponent(DomainModel):
    criterion: str
    weight: float = Field(ge=0)
    raw_score: float = Field(ge=0, le=1)
    weighted_score: float = Field(ge=0)
    rationale: str
    evidence_ids: list[UUID] = Field(default_factory=list)


class JobAnalysis(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    job_id: UUID
    policy_id: UUID
    hard_filter_passed: bool
    hard_filter_reasons: list[str] = Field(default_factory=list)
    total_score: float = Field(ge=0, le=100)
    components: list[ScoreComponent] = Field(default_factory=list)
    matched_evidence_ids: list[UUID] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    analyzed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Application(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    job_id: UUID
    status: ApplicationStatus = ApplicationStatus.DISCOVERED
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ApplicationEvent(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    application_id: UUID
    event_type: str
    from_status: ApplicationStatus | None = None
    to_status: ApplicationStatus | None = None
    actor: str
    detail: dict[str, object] = Field(default_factory=dict)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
