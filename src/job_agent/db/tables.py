from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from job_agent.db.base import Base


class CareerProfileRow(Base):
    __tablename__ = "career_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    professional_headline: Mapped[str | None] = mapped_column(String(300))
    summary: Mapped[str | None] = mapped_column(Text)


class ExperienceRow(Base):
    __tablename__ = "experiences"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("career_profiles.id", ondelete="CASCADE"), nullable=False
    )
    canonical_key: Mapped[str | None] = mapped_column(String(200), unique=True, index=True)
    employer: Mapped[str] = mapped_column(String(200), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date)
    location: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    verification_status: Mapped[str | None] = mapped_column(String(30), index=True)


class EvidenceItemRow(Base):
    __tablename__ = "evidence_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    evidence_key: Mapped[str | None] = mapped_column(String(80), unique=True, index=True)
    experience_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("experiences.id", ondelete="SET NULL")
    )
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    claim: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[str | None] = mapped_column(Text)
    metric: Mapped[str | None] = mapped_column(String(500))
    provenance: Mapped[str | None] = mapped_column(Text)
    verification_status: Mapped[str | None] = mapped_column(String(30), index=True)
    approval_status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft", index=True)
    resume_eligible: Mapped[bool] = mapped_column(nullable=False, default=False, index=True)
    resume_visibility: Mapped[str | None] = mapped_column(String(30), index=True)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String(100)), nullable=False, default=list)


class SkillRow(Base):
    __tablename__ = "skills"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)
    category: Mapped[str | None] = mapped_column(String(100))
    aliases: Mapped[list[str]] = mapped_column(ARRAY(String(150)), nullable=False, default=list)


class EvidenceSkillRow(Base):
    __tablename__ = "evidence_skills"
    __table_args__ = (UniqueConstraint("evidence_id", "skill_id"),)

    evidence_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evidence_items.id", ondelete="CASCADE"), primary_key=True
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True
    )


class CertificationRow(Base):
    __tablename__ = "certifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("career_profiles.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    issuer: Mapped[str] = mapped_column(String(200), nullable=False)
    issued_on: Mapped[date | None] = mapped_column(Date)
    expires_on: Mapped[date | None] = mapped_column(Date)
    credential_id: Mapped[str | None] = mapped_column(String(200))
    approval_status: Mapped[str] = mapped_column(String(30), nullable=False, default="approved")


class TargetingPolicyRow(Base):
    __tablename__ = "targeting_policies"
    __table_args__ = (UniqueConstraint("name", "version"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    version: Mapped[int] = mapped_column(nullable=False, default=1)
    active: Mapped[bool] = mapped_column(nullable=False, default=False)
    target_titles: Mapped[list[str]] = mapped_column(ARRAY(String(200)), nullable=False, default=list)
    target_seniority: Mapped[list[str]] = mapped_column(ARRAY(String(100)), nullable=False, default=list)
    allowed_locations: Mapped[list[str]] = mapped_column(ARRAY(String(200)), nullable=False, default=list)
    remote_allowed: Mapped[bool] = mapped_column(nullable=False, default=True)
    hybrid_allowed: Mapped[bool] = mapped_column(nullable=False, default=True)
    onsite_allowed: Mapped[bool] = mapped_column(nullable=False, default=False)
    minimum_base_salary_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    remote_minimum_base_salary_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    location_compensation_rules: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    required_terms: Mapped[list[str]] = mapped_column(ARRAY(String(150)), nullable=False, default=list)
    excluded_terms: Mapped[list[str]] = mapped_column(ARRAY(String(150)), nullable=False, default=list)
    weights: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class JobOpportunityRow(Base):
    __tablename__ = "job_opportunities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(300))
    source_url: Mapped[str | None] = mapped_column(Text)
    company: Mapped[str] = mapped_column(String(200), nullable=False)
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    location: Mapped[str | None] = mapped_column(String(250))
    compensation_text: Mapped[str | None] = mapped_column(Text)
    description_raw: Mapped[str] = mapped_column(Text, nullable=False)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    content_hash: Mapped[str | None] = mapped_column(String(64), index=True)


class JobRequirementRow(Base):
    __tablename__ = "job_requirements"
    __table_args__ = (UniqueConstraint("job_id", "ordinal"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_opportunities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    requirement_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    importance: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_skills: Mapped[list[str]] = mapped_column(ARRAY(String(150)), nullable=False, default=list)
    minimum_years: Mapped[int | None] = mapped_column(Integer)
    source_section: Mapped[str | None] = mapped_column(String(120))
    matched: Mapped[bool | None] = mapped_column(Boolean)


class JobAnalysisRow(Base):
    __tablename__ = "job_analyses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_opportunities.id", ondelete="CASCADE"), nullable=False
    )
    policy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("targeting_policies.id", ondelete="RESTRICT"), nullable=False
    )
    hard_filter_passed: Mapped[bool] = mapped_column(nullable=False)
    hard_filter_reasons: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    total_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    components: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    requirement_coverage: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    role_family: Mapped[str | None] = mapped_column(String(80))
    detected_seniority: Mapped[str | None] = mapped_column(String(40))
    location_context: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    matched_evidence_ids: Mapped[list[str]] = mapped_column(ARRAY(String(80)), nullable=False, default=list)
    gaps: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    unknowns: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ApplicationRow(Base):
    __tablename__ = "applications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_opportunities.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="discovered")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ApplicationEventRow(Base):
    __tablename__ = "application_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(40))
    to_status: Mapped[str | None] = mapped_column(String(40))
    actor: Mapped[str] = mapped_column(String(120), nullable=False)
    detail: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
