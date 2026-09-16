from __future__ import annotations

from collections import defaultdict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from job_agent.db.tables import (
    CareerProfileRow,
    CertificationRow,
    EvidenceItemRow,
    EvidenceSkillRow,
    ExperienceRow,
    SkillRow,
)
from job_agent.domain.enums import ApprovalStatus, ResumeVisibility, VerificationStatus
from job_agent.domain.models import CareerProfile, Certification, EvidenceItem, Experience, Skill
from job_agent.domain.retrieval import EvidenceRecord


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
