from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RequirementMatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requirement: str
    importance: str
    matched: bool
    confidence: float = Field(ge=0, le=1)
    evidence_ids: list[UUID] = Field(default_factory=list)
    rationale: str


class SemanticFitResult(BaseModel):
    """Typed output contract for the future JobMatchAgent."""

    model_config = ConfigDict(extra="forbid")

    role_family: str
    seniority_fit: float = Field(ge=0, le=1)
    domain_fit: float = Field(ge=0, le=1)
    skills_fit: float = Field(ge=0, le=1)
    leadership_fit: float = Field(ge=0, le=1)
    requirements: list[RequirementMatch] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
