from typing import Protocol
from uuid import UUID

from job_agent.domain.enums import ApprovalStatus, ResumeVisibility, VerificationStatus
from job_agent.domain.models import CareerProfile, Certification, Experience, JobOpportunity, Skill, TargetingPolicy
from job_agent.domain.retrieval import EvidenceRecord


class EvidenceRepository(Protocol):
    def get(self, identifier: UUID | str) -> EvidenceRecord | None: ...

    def list_records(
        self,
        *,
        experience_ids: list[UUID] | None = None,
        categories: list[str] | None = None,
        verification_statuses: list[VerificationStatus] | None = None,
        approval_statuses: list[ApprovalStatus] | None = None,
        resume_eligible: bool | None = None,
        resume_visibility: list[ResumeVisibility] | None = None,
    ) -> list[EvidenceRecord]: ...


class CareerRepository(Protocol):
    def get_profile(self) -> CareerProfile | None: ...
    def list_experiences(self) -> list[Experience]: ...
    def get_experience(self, experience_id: UUID) -> Experience | None: ...
    def list_skills(self) -> list[Skill]: ...
    def list_certifications(self) -> list[Certification]: ...


class JobRepository(Protocol):
    def get(self, job_id: UUID) -> JobOpportunity | None: ...
    def add(self, job: JobOpportunity) -> None: ...


class PolicyRepository(Protocol):
    def get_active(self) -> TargetingPolicy | None: ...
