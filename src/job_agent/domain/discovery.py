from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class DiscoveryProvider(StrEnum):
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    ASHBY = "ashby"


class DiscoveryRunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class DiscoverySourceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company: str = Field(min_length=1, max_length=200)
    provider: DiscoveryProvider
    board_identifier: str = Field(min_length=1, max_length=250)
    enabled: bool = True
    priority: int = Field(default=100, ge=1, le=1000)
    config: dict[str, object] = Field(default_factory=dict)


class DiscoverySourceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    company: str
    provider: DiscoveryProvider
    board_identifier: str
    enabled: bool
    priority: int
    config: dict[str, object]
    created_at: datetime
    last_checked_at: datetime | None = None


class DiscoveryPosting(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: DiscoveryProvider
    external_id: str
    company: str
    title: str
    location: str | None = None
    work_arrangement: str | None = None
    compensation_text: str | None = None
    description_raw: str = Field(min_length=1)
    source_url: HttpUrl | None = None
    apply_url: HttpUrl | None = None
    published_at: datetime | None = None
    employment_type: str | None = None


class DiscoveryRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: UUID | None = None
    analyze: bool = True
    minimum_surface_score: float = Field(default=80.0, ge=0, le=100)
    include_disabled: bool = False


class DiscoveryRunSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    source_id: UUID
    company: str
    provider: DiscoveryProvider
    status: DiscoveryRunStatus
    started_at: datetime
    completed_at: datetime | None = None
    postings_retrieved: int = 0
    title_candidates: int = 0
    jobs_created: int = 0
    jobs_updated: int = 0
    jobs_analyzed: int = 0
    hard_filter_passed: int = 0
    surfaced: int = 0
    postings_closed: int = 0
    error_message: str | None = None


class DiscoveryBatchSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runs: list[DiscoveryRunSummary] = Field(default_factory=list)

    @property
    def totals(self) -> dict[str, int]:
        fields = (
            "postings_retrieved",
            "title_candidates",
            "jobs_created",
            "jobs_updated",
            "jobs_analyzed",
            "hard_filter_passed",
            "surfaced",
            "postings_closed",
        )
        return {field: sum(getattr(run, field) for run in self.runs) for field in fields}




class DiscoveryCandidateSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: UUID
    company: str
    title: str
    location: str | None = None
    work_arrangement: str | None = None
    compensation_text: str | None = None
    source_url: str | None = None
    provider_source: str
    posting_status: str
    last_seen_at: datetime | None = None
    total_score: float
    hard_filter_passed: bool
    analyzed_at: datetime
    gaps: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)


class DiscoveryBatchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runs: list[DiscoveryRunSummary]
    totals: dict[str, int]
