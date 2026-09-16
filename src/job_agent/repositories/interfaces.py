from typing import Protocol
from uuid import UUID

from job_agent.domain.models import EvidenceItem, JobOpportunity, TargetingPolicy


class EvidenceRepository(Protocol):
    async def list_approved(self) -> list[EvidenceItem]: ...

    async def get_many(self, ids: list[UUID]) -> list[EvidenceItem]: ...


class JobRepository(Protocol):
    async def get(self, job_id: UUID) -> JobOpportunity | None: ...

    async def add(self, job: JobOpportunity) -> None: ...


class PolicyRepository(Protocol):
    async def get_active(self) -> TargetingPolicy | None: ...
