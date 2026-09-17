from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class RequirementType(StrEnum):
    QUALIFICATION = "qualification"
    RESPONSIBILITY = "responsibility"
    PREFERRED = "preferred"
    OTHER = "other"


class RequirementImportance(StrEnum):
    REQUIRED = "required"
    PREFERRED = "preferred"
    CONTEXT = "context"


class RequirementKind(StrEnum):
    SKILL = "skill"
    EXPERIENCE_YEARS = "experience_years"
    LEADERSHIP_YEARS = "leadership_years"
    OPERATING_MODEL = "operating_model"
    OTHER = "other"


class RequirementSkillMode(StrEnum):
    ALL = "all"
    ANY = "any"


class WorkArrangement(StrEnum):
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"
    UNKNOWN = "unknown"


class ParsedJobRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID | None = None
    ordinal: int = Field(ge=0)
    requirement_type: RequirementType
    importance: RequirementImportance
    text: str
    canonical_skills: list[str] = Field(default_factory=list)
    minimum_years: int | None = Field(default=None, ge=0, le=50)
    requirement_kind: RequirementKind = RequirementKind.SKILL
    skill_match_mode: RequirementSkillMode = RequirementSkillMode.ALL
    source_section: str | None = None
    matched: bool | None = None


class ParsedJobDescription(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role_family: str
    seniority: str | None = None
    work_arrangement: WorkArrangement = WorkArrangement.UNKNOWN
    requirements: list[ParsedJobRequirement] = Field(default_factory=list)
    discovered_skills: list[str] = Field(default_factory=list)
    minimum_years: int | None = None


class JobIngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str = "manual"
    external_id: str | None = None
    source_url: HttpUrl | None = None
    company: str
    title: str
    location: str | None = None
    compensation_text: str | None = None
    work_arrangement: WorkArrangement | None = None
    description_raw: str = Field(min_length=20)


class JobIngestResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: UUID
    created: bool
    content_hash: str
    parsed: ParsedJobDescription


class JobSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    source: str
    external_id: str | None
    source_url: str | None
    company: str
    title: str
    location: str | None
    compensation_text: str | None
    work_arrangement: WorkArrangement | None = None
    discovered_at: datetime
    content_hash: str | None


class LocationCompensationRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    zone: str
    name: str
    locations: list[str] = Field(default_factory=list)
    minimum_base_salary_usd: float = Field(ge=0)


class LocationCompensationDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw_location: str | None = None
    normalized_city: str | None = None
    commute_zone: str | None = None
    work_arrangement: WorkArrangement
    required_minimum_base_salary_usd: float | None = None
    published_max_base_salary_usd: float | None = None
    salary_passed: bool | None = None
    manual_review_required: bool = False
    rationale: str


class TargetingPolicyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    version: int = Field(default=1, ge=1)
    active: bool = False
    target_titles: list[str] = Field(default_factory=list)
    target_seniority: list[str] = Field(default_factory=list)
    allowed_locations: list[str] = Field(default_factory=list)
    remote_allowed: bool = True
    hybrid_allowed: bool = True
    onsite_allowed: bool = False
    minimum_base_salary_usd: float | None = Field(default=None, ge=0)
    remote_minimum_base_salary_usd: float | None = Field(default=None, ge=0)
    location_compensation_rules: list[LocationCompensationRule] = Field(default_factory=list)
    required_terms: list[str] = Field(default_factory=list)
    excluded_terms: list[str] = Field(default_factory=list)
    weights: dict[str, float] = Field(default_factory=dict)


class RequirementCoverage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ordinal: int
    requirement: str
    importance: RequirementImportance
    requirement_kind: RequirementKind = RequirementKind.SKILL
    skill_match_mode: RequirementSkillMode = RequirementSkillMode.ALL
    canonical_skills: list[str]
    recognized: bool = True
    matched: bool
    evidence_keys: list[str] = Field(default_factory=list)
    score: float = Field(ge=0, le=100)
    rationale: str
    # Tenure requirements are deliberately represented as threshold proofs rather
    # than pseudo-precise decimal-year claims. These fields preserve the audit
    # trail needed to understand why a threshold passed without asserting an
    # exact amount of specialized experience.
    minimum_years: int | None = Field(default=None, ge=0, le=50)
    tenure_threshold_met: bool | None = None
    qualifying_experience_keys: list[str] = Field(default_factory=list)




class MatchConfidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    required_total: int = 0
    required_recognized: int = 0
    required_matched: int = 0
    required_unknown: int = 0
    preferred_total: int = 0
    preferred_recognized: int = 0
    preferred_matched: int = 0
    recognized_required_pct: float = Field(default=100.0, ge=0, le=100)
    matched_required_pct: float = Field(default=0.0, ge=0, le=100)
    matched_preferred_pct: float = Field(default=0.0, ge=0, le=100)
    overall_confidence: float = Field(default=100.0, ge=0, le=100)
    manual_review_required: bool = False

class JobMatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_id: UUID | None = None
    resume_safe_only: bool = True
    max_evidence_per_requirement: int = Field(default=3, ge=1, le=10)


class JobMatchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analysis_id: UUID
    job_id: UUID
    policy_id: UUID
    hard_filter_passed: bool
    hard_filter_reasons: list[str]
    total_score: float = Field(ge=0, le=100)
    role_family: str
    seniority: str | None
    requirement_coverage: list[RequirementCoverage]
    matched_evidence_keys: list[str]
    gaps: list[str]
    unknowns: list[str]
    components: dict[str, float]
    confidence: MatchConfidence
    location_compensation: LocationCompensationDecision


class PolicyActivationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_id: UUID


class PolicySummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    name: str
    version: int
    active: bool
    target_titles: list[str]
    target_seniority: list[str]
    allowed_locations: list[str]
    remote_allowed: bool
    hybrid_allowed: bool
    onsite_allowed: bool
    minimum_base_salary_usd: float | None
    remote_minimum_base_salary_usd: float | None
    location_compensation_rules: list[LocationCompensationRule]
    required_terms: list[str]
    excluded_terms: list[str]
    weights: dict[str, float]
