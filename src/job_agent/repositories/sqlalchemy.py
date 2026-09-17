from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from job_agent.db.tables import (
    CareerProfileRow,
    CertificationRow,
    EvidenceItemRow,
    EvidenceSkillRow,
    DiscoveryRunRow,
    DiscoverySourceRow,
    ExperienceRow,
    JobAnalysisRow,
    JobOpportunityRow,
    JobRequirementRow,
    SkillRow,
    TargetingPolicyRow,
)
from job_agent.domain.discovery import (
    DiscoveryCandidateSummary,
    DiscoveryProvider,
    DiscoveryRunStatus,
    DiscoveryRunSummary,
    DiscoverySourceCreate,
    DiscoverySourceSummary,
)
from job_agent.domain.enums import ApprovalStatus, ResumeVisibility, VerificationStatus
from job_agent.domain.jobs import (
    JobMatchResponse,
    LocationCompensationDecision,
    MatchConfidence,
    ParsedJobRequirement,
    RequirementCoverage,
    RequirementImportance,
    RequirementKind,
    RequirementSkillMode,
    RequirementType,
)
from job_agent.domain.models import (
    CareerProfile,
    Certification,
    EvidenceItem,
    Experience,
    JobAnalysis,
    JobOpportunity,
    ScoreComponent,
    Skill,
    TargetingPolicy,
)
from job_agent.domain.retrieval import EvidenceRecord
from job_agent.services.role_preferences import evaluate_role_preferences


def _profile(row: CareerProfileRow) -> CareerProfile:
    return CareerProfile(
        id=row.id,
        display_name=row.display_name,
        professional_headline=row.professional_headline,
        summary=row.summary,
    )


def _experience(row: ExperienceRow) -> Experience:
    return Experience(
        id=row.id,
        canonical_key=row.canonical_key,
        profile_id=row.profile_id,
        employer=row.employer,
        title=row.title,
        start_date=row.start_date,
        end_date=row.end_date,
        location=row.location,
        description=row.description,
        verification_status=row.verification_status,
    )


def _evidence(row: EvidenceItemRow) -> EvidenceItem:
    return EvidenceItem(
        id=row.id,
        evidence_key=row.evidence_key,
        experience_id=row.experience_id,
        category=row.category,
        claim=row.claim,
        context=row.context,
        metric=row.metric,
        provenance=row.provenance,
        verification_status=row.verification_status,
        approval_status=row.approval_status,
        resume_eligible=row.resume_eligible,
        resume_visibility=row.resume_visibility,
        tags=set(row.tags or []),
    )


def _skill(row: SkillRow) -> Skill:
    return Skill(
        id=row.id,
        name=row.name,
        category=row.category,
        aliases=set(row.aliases or []),
    )


def _certification(row: CertificationRow) -> Certification:
    return Certification(
        id=row.id,
        profile_id=row.profile_id,
        name=row.name,
        issuer=row.issuer,
        issued_on=row.issued_on,
        expires_on=row.expires_on,
        credential_id=row.credential_id,
        approval_status=row.approval_status,
    )


class SqlAlchemyCareerRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_profile(self) -> CareerProfile | None:
        row = self.session.execute(select(CareerProfileRow).limit(1)).scalar_one_or_none()
        return _profile(row) if row else None

    def list_experiences(self) -> list[Experience]:
        rows = self.session.execute(
            select(ExperienceRow).order_by(ExperienceRow.start_date.desc(), ExperienceRow.employer)
        ).scalars()
        return [_experience(row) for row in rows]

    def get_experience(self, experience_id: UUID) -> Experience | None:
        row = self.session.get(ExperienceRow, experience_id)
        return _experience(row) if row else None

    def list_skills(self) -> list[Skill]:
        rows = self.session.execute(select(SkillRow).order_by(SkillRow.name)).scalars()
        return [_skill(row) for row in rows]

    def list_certifications(self) -> list[Certification]:
        rows = self.session.execute(
            select(CertificationRow).order_by(CertificationRow.issued_on.desc().nullslast())
        ).scalars()
        return [_certification(row) for row in rows]


class SqlAlchemyEvidenceRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, identifier: UUID | str) -> EvidenceRecord | None:
        stmt = select(EvidenceItemRow)
        if isinstance(identifier, UUID):
            stmt = stmt.where(EvidenceItemRow.id == identifier)
        else:
            stmt = stmt.where(EvidenceItemRow.evidence_key == identifier)
        row = self.session.execute(stmt).scalar_one_or_none()
        if not row:
            return None
        return self._hydrate([row])[0]

    def list_records(
        self,
        *,
        experience_ids: list[UUID] | None = None,
        categories: list[str] | None = None,
        verification_statuses: list[VerificationStatus] | None = None,
        approval_statuses: list[ApprovalStatus] | None = None,
        resume_eligible: bool | None = None,
        resume_visibility: list[ResumeVisibility] | None = None,
    ) -> list[EvidenceRecord]:
        stmt = select(EvidenceItemRow)
        if experience_ids:
            stmt = stmt.where(EvidenceItemRow.experience_id.in_(experience_ids))
        if categories:
            stmt = stmt.where(EvidenceItemRow.category.in_(categories))
        if verification_statuses:
            stmt = stmt.where(
                EvidenceItemRow.verification_status.in_([status.value for status in verification_statuses])
            )
        if approval_statuses:
            stmt = stmt.where(
                EvidenceItemRow.approval_status.in_([status.value for status in approval_statuses])
            )
        if resume_eligible is not None:
            stmt = stmt.where(EvidenceItemRow.resume_eligible.is_(resume_eligible))
        if resume_visibility:
            stmt = stmt.where(
                EvidenceItemRow.resume_visibility.in_([visibility.value for visibility in resume_visibility])
            )
        rows = list(self.session.execute(stmt).scalars())
        return self._hydrate(rows)

    def _hydrate(self, rows: list[EvidenceItemRow]) -> list[EvidenceRecord]:
        if not rows:
            return []

        experience_ids = {row.experience_id for row in rows if row.experience_id is not None}
        experiences: dict[UUID, Experience] = {}
        if experience_ids:
            exp_rows = self.session.execute(
                select(ExperienceRow).where(ExperienceRow.id.in_(experience_ids))
            ).scalars()
            experiences = {row.id: _experience(row) for row in exp_rows}

        evidence_ids = [row.id for row in rows]
        skill_rows = self.session.execute(
            select(EvidenceSkillRow.evidence_id, SkillRow)
            .join(SkillRow, SkillRow.id == EvidenceSkillRow.skill_id)
            .where(EvidenceSkillRow.evidence_id.in_(evidence_ids))
            .order_by(SkillRow.name)
        ).all()
        skills_by_evidence: dict[UUID, list[Skill]] = defaultdict(list)
        for evidence_id, skill_row in skill_rows:
            skills_by_evidence[evidence_id].append(_skill(skill_row))

        return [
            EvidenceRecord(
                evidence=_evidence(row),
                experience=experiences.get(row.experience_id),
                skills=skills_by_evidence.get(row.id, []),
            )
            for row in rows
        ]



def _job(row: JobOpportunityRow) -> JobOpportunity:
    return JobOpportunity(
        id=row.id,
        source=row.source,
        external_id=row.external_id,
        source_url=row.source_url,
        company=row.company,
        title=row.title,
        location=row.location,
        compensation_text=row.compensation_text,
        work_arrangement=row.work_arrangement,
        description_raw=row.description_raw,
        content_hash=row.content_hash,
        discovered_at=row.discovered_at,
    )


def _policy(row: TargetingPolicyRow) -> TargetingPolicy:
    return TargetingPolicy(
        id=row.id,
        name=row.name,
        version=row.version,
        active=row.active,
        target_titles=list(row.target_titles or []),
        target_seniority=list(row.target_seniority or []),
        allowed_locations=list(row.allowed_locations or []),
        remote_allowed=row.remote_allowed,
        hybrid_allowed=row.hybrid_allowed,
        onsite_allowed=row.onsite_allowed,
        minimum_base_salary_usd=row.minimum_base_salary_usd,
        remote_minimum_base_salary_usd=row.remote_minimum_base_salary_usd,
        location_compensation_rules=list(row.location_compensation_rules or []),
        required_terms=set(row.required_terms or []),
        excluded_terms=set(row.excluded_terms or []),
        excluded_title_terms=set(row.excluded_title_terms or []),
        exclude_software_engineering_roles=bool(row.exclude_software_engineering_roles),
        exclude_heavy_coding_roles=bool(row.exclude_heavy_coding_roles),
        weights=dict(row.weights or {}),
    )


def _requirement(row: JobRequirementRow) -> ParsedJobRequirement:
    return ParsedJobRequirement(
        id=row.id,
        ordinal=row.ordinal,
        requirement_type=RequirementType(row.requirement_type),
        importance=RequirementImportance(row.importance),
        text=row.text,
        canonical_skills=list(row.canonical_skills or []),
        minimum_years=row.minimum_years,
        requirement_kind=RequirementKind(row.requirement_kind or "skill"),
        skill_match_mode=RequirementSkillMode(row.skill_match_mode or "all"),
        source_section=row.source_section,
        matched=row.matched,
    )


def _analysis(row: JobAnalysisRow) -> JobAnalysis:
    components = []
    for item in row.components or []:
        # v0.3 persists score components with stable evidence keys. JobAnalysis's
        # legacy ScoreComponent model is retained for backwards compatibility,
        # while evidence ids are omitted here because the stable keys live in
        # matched_evidence_ids and the API match response.
        components.append(
            ScoreComponent(
                criterion=str(item.get("criterion", "component")),
                weight=float(item.get("weight", 0)),
                raw_score=float(item.get("raw_score", 0)),
                weighted_score=float(item.get("weighted_score", 0)),
                rationale=str(item.get("rationale", "")),
                evidence_ids=[],
            )
        )
    return JobAnalysis(
        id=row.id,
        job_id=row.job_id,
        policy_id=row.policy_id,
        hard_filter_passed=row.hard_filter_passed,
        hard_filter_reasons=list(row.hard_filter_reasons or []),
        total_score=float(row.total_score),
        components=components,
        matched_evidence_ids=[],
        gaps=list(row.gaps or []),
        unknowns=list(row.unknowns or []),
        analyzed_at=row.analyzed_at,
    )


class SqlAlchemyJobRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, job_id: UUID) -> JobOpportunity | None:
        row = self.session.get(JobOpportunityRow, job_id)
        return _job(row) if row else None

    def list(self, limit: int = 100) -> list[JobOpportunity]:
        rows = self.session.execute(
            select(JobOpportunityRow)
            .order_by(JobOpportunityRow.discovered_at.desc())
            .limit(limit)
        ).scalars()
        return [_job(row) for row in rows]

    def upsert(self, job: JobOpportunity, content_hash: str) -> tuple[JobOpportunity, bool]:
        row = None
        if job.external_id:
            row = self.session.execute(
                select(JobOpportunityRow).where(
                    JobOpportunityRow.source == job.source,
                    JobOpportunityRow.external_id == job.external_id,
                )
            ).scalar_one_or_none()
        if row is None:
            row = self.session.execute(
                select(JobOpportunityRow).where(
                    JobOpportunityRow.company == job.company,
                    JobOpportunityRow.title == job.title,
                    JobOpportunityRow.content_hash == content_hash,
                )
            ).scalar_one_or_none()

        created = row is None
        if row is None:
            row = JobOpportunityRow(
                id=job.id,
                source=job.source,
                external_id=job.external_id,
                source_url=str(job.source_url) if job.source_url else None,
                company=job.company,
                title=job.title,
                location=job.location,
                compensation_text=job.compensation_text,
                work_arrangement=job.work_arrangement,
                description_raw=job.description_raw,
                discovered_at=job.discovered_at,
                content_hash=content_hash,
            )
            self.session.add(row)
        else:
            row.source_url = str(job.source_url) if job.source_url else row.source_url
            row.location = job.location
            row.compensation_text = job.compensation_text
            row.work_arrangement = job.work_arrangement
            row.description_raw = job.description_raw
            row.content_hash = content_hash
        self.session.flush()
        return _job(row), created

    def replace_requirements(
        self, job_id: UUID, requirements: list[ParsedJobRequirement]
    ) -> list[ParsedJobRequirement]:
        self.session.execute(delete(JobRequirementRow).where(JobRequirementRow.job_id == job_id))
        rows: list[JobRequirementRow] = []
        for req in requirements:
            row = JobRequirementRow(
                job_id=job_id,
                ordinal=req.ordinal,
                requirement_type=req.requirement_type.value,
                importance=req.importance.value,
                text=req.text,
                canonical_skills=list(req.canonical_skills),
                minimum_years=req.minimum_years,
                requirement_kind=req.requirement_kind.value,
                skill_match_mode=req.skill_match_mode.value,
                source_section=req.source_section,
                matched=req.matched,
            )
            self.session.add(row)
            rows.append(row)
        self.session.flush()
        return [_requirement(row) for row in rows]

    def list_requirements(self, job_id: UUID) -> list[ParsedJobRequirement]:
        rows = self.session.execute(
            select(JobRequirementRow)
            .where(JobRequirementRow.job_id == job_id)
            .order_by(JobRequirementRow.ordinal)
        ).scalars()
        return [_requirement(row) for row in rows]

    def set_requirement_matches(self, job_id: UUID, matched_ordinals: set[int]) -> None:
        rows = self.session.execute(
            select(JobRequirementRow).where(JobRequirementRow.job_id == job_id)
        ).scalars()
        for row in rows:
            row.matched = row.ordinal in matched_ordinals
        self.session.flush()

    def save_analysis(
        self,
        analysis: JobAnalysis,
        *,
        stable_evidence_keys: list[str] | None = None,
        requirement_coverage: list[RequirementCoverage] | None = None,
        role_family: str | None = None,
        seniority: str | None = None,
        location_context: dict | None = None,
        confidence_context: dict | None = None,
    ) -> JobAnalysis:
        row = JobAnalysisRow(
            id=analysis.id,
            job_id=analysis.job_id,
            policy_id=analysis.policy_id,
            hard_filter_passed=analysis.hard_filter_passed,
            hard_filter_reasons=list(analysis.hard_filter_reasons),
            total_score=analysis.total_score,
            components=[component.model_dump(mode="json") for component in analysis.components],
            requirement_coverage=[
                item.model_dump(mode="json") for item in (requirement_coverage or [])
            ],
            role_family=role_family,
            detected_seniority=seniority,
            location_context=dict(location_context or {}),
            confidence_context=dict(confidence_context or {}),
            matched_evidence_ids=list(stable_evidence_keys or []),
            gaps=list(analysis.gaps),
            unknowns=list(analysis.unknowns),
            analyzed_at=analysis.analyzed_at,
        )
        self.session.add(row)
        self.session.flush()
        return analysis

    def latest_analysis(self, job_id: UUID) -> JobAnalysis | None:
        row = self.session.execute(
            select(JobAnalysisRow)
            .where(JobAnalysisRow.job_id == job_id)
            .order_by(JobAnalysisRow.analyzed_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        return _analysis(row) if row else None

    def latest_match_response(self, job_id: UUID) -> JobMatchResponse | None:
        row = self.session.execute(
            select(JobAnalysisRow)
            .where(JobAnalysisRow.job_id == job_id)
            .order_by(JobAnalysisRow.analyzed_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        if row is None:
            return None
        coverage = [RequirementCoverage.model_validate(item) for item in (row.requirement_coverage or [])]
        components = {
            str(item.get("criterion")): round(float(item.get("raw_score", 0)) * 100, 2)
            for item in (row.components or [])
        }
        return JobMatchResponse(
            analysis_id=row.id,
            job_id=row.job_id,
            policy_id=row.policy_id,
            hard_filter_passed=row.hard_filter_passed,
            hard_filter_reasons=list(row.hard_filter_reasons or []),
            total_score=float(row.total_score),
            role_family=row.role_family or "other",
            seniority=row.detected_seniority,
            requirement_coverage=coverage,
            matched_evidence_keys=list(row.matched_evidence_ids or []),
            gaps=list(row.gaps or []),
            unknowns=list(row.unknowns or []),
            components=components,
            confidence=MatchConfidence.model_validate(row.confidence_context or {
                "manual_review_required": True,
                "overall_confidence": 50.0,
            }),
            location_compensation=LocationCompensationDecision.model_validate(row.location_context or {
                "work_arrangement": "unknown",
                "manual_review_required": True,
                "rationale": "Location/compensation context was not persisted for this older analysis.",
            }),
        )


def _discovery_source(row: DiscoverySourceRow) -> DiscoverySourceSummary:
    return DiscoverySourceSummary(
        id=row.id,
        company=row.company,
        provider=DiscoveryProvider(row.provider),
        board_identifier=row.board_identifier,
        enabled=row.enabled,
        priority=row.priority,
        config=dict(row.config or {}),
        created_at=row.created_at,
        last_checked_at=row.last_checked_at,
    )


def _discovery_run(row: DiscoveryRunRow, source: DiscoverySourceRow) -> DiscoveryRunSummary:
    return DiscoveryRunSummary(
        id=row.id,
        source_id=row.source_id,
        company=source.company,
        provider=DiscoveryProvider(source.provider),
        status=DiscoveryRunStatus(row.status),
        started_at=row.started_at,
        completed_at=row.completed_at,
        postings_retrieved=row.postings_retrieved,
        title_candidates=row.title_candidates,
        jobs_created=row.jobs_created,
        jobs_updated=row.jobs_updated,
        jobs_analyzed=row.jobs_analyzed,
        hard_filter_passed=row.hard_filter_passed,
        surfaced=row.surfaced,
        postings_closed=row.postings_closed,
        error_message=row.error_message,
    )


class SqlAlchemyDiscoveryRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add_source(self, source: DiscoverySourceCreate) -> DiscoverySourceSummary:
        existing = self.session.execute(
            select(DiscoverySourceRow).where(
                DiscoverySourceRow.provider == source.provider.value,
                DiscoverySourceRow.board_identifier == source.board_identifier,
            )
        ).scalar_one_or_none()
        if existing is not None:
            existing.company = source.company.strip()
            existing.enabled = source.enabled
            existing.priority = source.priority
            existing.config = dict(source.config)
            self.session.flush()
            return _discovery_source(existing)
        row = DiscoverySourceRow(
            id=uuid4(),
            company=source.company.strip(),
            provider=source.provider.value,
            board_identifier=source.board_identifier.strip(),
            enabled=source.enabled,
            priority=source.priority,
            config=dict(source.config),
            created_at=datetime.now(timezone.utc),
        )
        self.session.add(row)
        self.session.flush()
        return _discovery_source(row)

    def get_source(self, source_id: UUID) -> DiscoverySourceSummary | None:
        row = self.session.get(DiscoverySourceRow, source_id)
        return _discovery_source(row) if row else None

    def list_sources(self, *, enabled_only: bool = False) -> list[DiscoverySourceSummary]:
        stmt = select(DiscoverySourceRow)
        if enabled_only:
            stmt = stmt.where(DiscoverySourceRow.enabled.is_(True))
        rows = self.session.execute(
            stmt.order_by(DiscoverySourceRow.priority, DiscoverySourceRow.company)
        ).scalars()
        return [_discovery_source(row) for row in rows]

    def touch_source(self, source_id: UUID, checked_at: datetime) -> None:
        row = self.session.get(DiscoverySourceRow, source_id)
        if row:
            row.last_checked_at = checked_at
            self.session.flush()

    def start_run(self, source_id: UUID, started_at: datetime) -> UUID:
        row = DiscoveryRunRow(
            id=uuid4(),
            source_id=source_id,
            status=DiscoveryRunStatus.RUNNING.value,
            started_at=started_at,
        )
        self.session.add(row)
        self.session.flush()
        return row.id

    def finish_run(
        self,
        *,
        run_id: UUID,
        completed_at: datetime,
        status: DiscoveryRunStatus,
        counters: dict[str, int],
        error_message: str | None,
    ) -> DiscoveryRunSummary:
        row = self.session.get(DiscoveryRunRow, run_id)
        if row is None:
            raise LookupError("discovery run not found")
        row.status = status.value
        row.completed_at = completed_at
        row.error_message = error_message
        for field in (
            "postings_retrieved", "title_candidates", "jobs_created", "jobs_updated",
            "jobs_analyzed", "hard_filter_passed", "surfaced", "postings_closed",
        ):
            setattr(row, field, int(counters.get(field, 0)))
        source = self.session.get(DiscoverySourceRow, row.source_id)
        if source is None:
            raise LookupError("discovery source not found")
        self.session.flush()
        return _discovery_run(row, source)

    def list_runs(self, limit: int = 100) -> list[DiscoveryRunSummary]:
        rows = self.session.execute(
            select(DiscoveryRunRow, DiscoverySourceRow)
            .join(DiscoverySourceRow, DiscoverySourceRow.id == DiscoveryRunRow.source_id)
            .order_by(DiscoveryRunRow.started_at.desc())
            .limit(limit)
        ).all()
        return [_discovery_run(run, source) for run, source in rows]

    def list_candidates(
        self, *, minimum_score: float = 80.0, limit: int = 100, open_only: bool = True
    ) -> list[DiscoveryCandidateSummary]:
        jobs_stmt = select(JobOpportunityRow).where(JobOpportunityRow.discovery_source_id.is_not(None))
        if open_only:
            jobs_stmt = jobs_stmt.where(JobOpportunityRow.posting_status == "open")
        jobs = list(self.session.execute(jobs_stmt).scalars())
        policy_row = self.session.execute(
            select(TargetingPolicyRow)
            .where(TargetingPolicyRow.active.is_(True))
            .order_by(TargetingPolicyRow.version.desc())
            .limit(1)
        ).scalar_one_or_none()
        active_policy = _policy(policy_row) if policy_row is not None else None
        candidates: list[DiscoveryCandidateSummary] = []
        for job in jobs:
            role_pref = evaluate_role_preferences(
                title=job.title,
                description=job.description_raw,
                policy=active_policy,
            )
            if not role_pref.accepted:
                continue
            analysis = self.session.execute(
                select(JobAnalysisRow)
                .where(JobAnalysisRow.job_id == job.id)
                .order_by(JobAnalysisRow.analyzed_at.desc())
                .limit(1)
            ).scalar_one_or_none()
            if analysis is None or not analysis.hard_filter_passed or float(analysis.total_score) < minimum_score:
                continue
            candidates.append(
                DiscoveryCandidateSummary(
                    job_id=job.id,
                    company=job.company,
                    title=job.title,
                    location=job.location,
                    work_arrangement=job.work_arrangement,
                    compensation_text=job.compensation_text,
                    source_url=job.source_url,
                    provider_source=job.source,
                    posting_status=job.posting_status,
                    last_seen_at=job.last_seen_at,
                    total_score=float(analysis.total_score),
                    hard_filter_passed=analysis.hard_filter_passed,
                    analyzed_at=analysis.analyzed_at,
                    gaps=list(analysis.gaps or []),
                    unknowns=list(analysis.unknowns or []),
                )
            )
        candidates.sort(key=lambda item: (item.total_score, item.analyzed_at), reverse=True)
        return candidates[:limit]

    def link_job(self, *, job_id: UUID, source_id: UUID, seen_at: datetime) -> None:
        row = self.session.get(JobOpportunityRow, job_id)
        if row is None:
            raise LookupError("job not found")
        row.discovery_source_id = source_id
        row.last_seen_at = seen_at
        row.posting_status = "open"
        self.session.flush()

    def mark_unseen_closed(
        self, *, source_id: UUID, seen_external_ids: set[str], seen_at: datetime
    ) -> int:
        stmt = select(JobOpportunityRow).where(
            JobOpportunityRow.discovery_source_id == source_id,
            JobOpportunityRow.posting_status == "open",
        )
        rows = list(self.session.execute(stmt).scalars())
        changed = 0
        for row in rows:
            if row.external_id and row.external_id not in seen_external_ids:
                # Only close postings that existed before this run. Jobs first linked during
                # this run are always in seen_external_ids, so this also protects partial runs.
                if row.last_seen_at is None or row.last_seen_at < seen_at:
                    row.posting_status = "closed"
                    changed += 1
        if changed:
            self.session.flush()
        return changed


class SqlAlchemyPolicyRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, policy_id: UUID) -> TargetingPolicy | None:
        row = self.session.get(TargetingPolicyRow, policy_id)
        return _policy(row) if row else None

    def get_active(self) -> TargetingPolicy | None:
        row = self.session.execute(
            select(TargetingPolicyRow)
            .where(TargetingPolicyRow.active.is_(True))
            .order_by(TargetingPolicyRow.version.desc())
            .limit(1)
        ).scalar_one_or_none()
        return _policy(row) if row else None

    def list(self) -> list[TargetingPolicy]:
        rows = self.session.execute(
            select(TargetingPolicyRow).order_by(TargetingPolicyRow.name, TargetingPolicyRow.version.desc())
        ).scalars()
        return [_policy(row) for row in rows]

    def add(self, policy: TargetingPolicy, active: bool = False) -> TargetingPolicy:
        if active:
            self.session.execute(update(TargetingPolicyRow).values(active=False))
        row = TargetingPolicyRow(
            id=policy.id,
            name=policy.name,
            version=policy.version,
            active=active,
            target_titles=list(policy.target_titles),
            target_seniority=list(policy.target_seniority),
            allowed_locations=list(policy.allowed_locations),
            remote_allowed=policy.remote_allowed,
            hybrid_allowed=policy.hybrid_allowed,
            onsite_allowed=policy.onsite_allowed,
            minimum_base_salary_usd=policy.minimum_base_salary_usd,
            remote_minimum_base_salary_usd=policy.remote_minimum_base_salary_usd,
            location_compensation_rules=[rule.model_dump(mode="json") for rule in policy.location_compensation_rules],
            required_terms=sorted(policy.required_terms),
            excluded_terms=sorted(policy.excluded_terms),
            excluded_title_terms=sorted(policy.excluded_title_terms),
            exclude_software_engineering_roles=policy.exclude_software_engineering_roles,
            exclude_heavy_coding_roles=policy.exclude_heavy_coding_roles,
            weights=dict(policy.weights),
        )
        self.session.add(row)
        self.session.flush()
        return _policy(row)

    def activate(self, policy_id: UUID) -> TargetingPolicy | None:
        row = self.session.get(TargetingPolicyRow, policy_id)
        if row is None:
            return None
        self.session.execute(update(TargetingPolicyRow).values(active=False))
        row.active = True
        self.session.flush()
        return _policy(row)
