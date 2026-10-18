"""API contracts for user-submitted job opportunities."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from job_agent.domain.jobs import JobIngestResponse, JobMatchResponse, WorkArrangement


class ManualJobIntakeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_url: HttpUrl | None = None
    description_raw: str | None = Field(default=None, max_length=120_000)
    company: str | None = Field(default=None, max_length=200)
    title: str | None = Field(default=None, max_length=250)
    location: str | None = Field(default=None, max_length=250)
    compensation_text: str | None = Field(default=None, max_length=500)
    work_arrangement: WorkArrangement | None = None

    @model_validator(mode="after")
    def validate_source(self) -> "ManualJobIntakeRequest":
        if not self.source_url and not (self.description_raw and self.description_raw.strip()):
            raise ValueError("Provide source_url or description_raw")
        if self.description_raw and self.description_raw.strip():
            if len(self.description_raw.strip()) < 20:
                raise ValueError("description_raw must contain at least 20 characters")
            if not (self.company and self.company.strip() and self.title and self.title.strip()):
                raise ValueError("Pasted descriptions require company and title")
        return self


class ManualJobIntakeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ingestion: JobIngestResponse
    analysis: JobMatchResponse
    extraction_method: str
    canonical_duplicate: bool
    notification_suppressed: bool
