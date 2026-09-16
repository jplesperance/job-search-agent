from __future__ import annotations

from uuid import UUID, uuid4

from job_agent.domain.enums import ApprovalStatus, ResumeVisibility, VerificationStatus
from job_agent.domain.models import CareerProfile, Certification, EvidenceItem, Experience, Skill
from job_agent.domain.retrieval import EvidenceRecord, EvidenceSearchRequest, MatchMode, RetrievalScope
from job_agent.services.evidence_search import EvidenceSearchService


class FakeCareerRepository:
    def __init__(self, skills: list[Skill]) -> None:
        self._skills = skills

    def get_profile(self) -> CareerProfile | None:
        return None

    def list_experiences(self) -> list[Experience]:
        return []

    def get_experience(self, experience_id: UUID) -> Experience | None:
        return None

    def list_skills(self) -> list[Skill]:
        return self._skills

    def list_certifications(self) -> list[Certification]:
        return []


class FakeEvidenceRepository:
    def __init__(self, records: list[EvidenceRecord]) -> None:
        self.records = records
        self.last_filters: dict | None = None

    def get(self, identifier: UUID | str) -> EvidenceRecord | None:
        for record in self.records:
            if identifier in {record.evidence.id, record.evidence.evidence_key}:
                return record
        return None

    def list_records(self, **filters) -> list[EvidenceRecord]:
        self.last_filters = filters
        result = list(self.records)
        if filters.get("resume_eligible") is not None:
            result = [
                record
                for record in result
                if record.evidence.resume_eligible is filters["resume_eligible"]
            ]
        if filters.get("resume_visibility"):
            allowed = set(filters["resume_visibility"])
            result = [record for record in result if record.evidence.resume_visibility in allowed]
        return result


def _fixture_service() -> tuple[EvidenceSearchService, FakeEvidenceRepository]:
    appsec = Skill(id=uuid4(), name="Application Security", category="security", aliases={"AppSec"})
    threat = Skill(id=uuid4(), name="Threat Modeling", category="security", aliases={"Threat Model"})
    ai = Skill(id=uuid4(), name="AI/LLM Security", category="security", aliases={"AI Security"})

    tiktok = Experience(
        id=uuid4(),
        canonical_key="tiktok-usds-2025-present",
        profile_id=uuid4(),
        employer="TikTok USDS",
        title="Senior SSDLC Specialist / Tech-Lead",
        start_date="2025-11-01",
        verification_status=VerificationStatus.CORROBORATED,
    )

    records = [
        EvidenceRecord(
            evidence=EvidenceItem(
                id=uuid4(),
                evidence_key="TT-AISEC-001",
                experience_id=tiktok.id,
                category="ai_security",
                claim="Performed AI/LLM security reviews using threat modeling.",
                verification_status=VerificationStatus.USER_VERIFIED,
                approval_status=ApprovalStatus.APPROVED,
                resume_eligible=True,
                resume_visibility=ResumeVisibility.PUBLIC_SAFE,
                tags={"AI/LLM Security", "Threat Modeling"},
            ),
            experience=tiktok,
            skills=[ai, threat, appsec],
        ),
        EvidenceRecord(
            evidence=EvidenceItem(
                id=uuid4(),
                evidence_key="TT-INT-001",
                experience_id=tiktok.id,
                category="internal",
                claim="Internal-only operational detail.",
                verification_status=VerificationStatus.USER_VERIFIED,
                approval_status=ApprovalStatus.APPROVED,
                resume_eligible=True,
                resume_visibility=ResumeVisibility.INTERNAL_ONLY,
                tags={"Application Security"},
            ),
            experience=tiktok,
            skills=[appsec],
        ),
    ]

    evidence_repo = FakeEvidenceRepository(records)
    service = EvidenceSearchService(evidence_repo, FakeCareerRepository([appsec, threat, ai]))
    return service, evidence_repo


def test_search_resolves_alias_and_returns_stable_evidence_key():
    service, _ = _fixture_service()
    response = service.search(
        EvidenceSearchRequest(skills=["AI Security", "Threat Model"], match_mode=MatchMode.ALL)
    )

    assert response.unknown_skills == []
    assert response.count == 1
    assert response.results[0].evidence_key == "TT-AISEC-001"
    assert response.results[0].score == 100.0
    assert set(response.results[0].matched_skills) == {"AI/LLM Security", "Threat Modeling"}


def test_resume_scope_forces_resume_safe_filters():
    service, repo = _fixture_service()
    response = service.search(
        EvidenceSearchRequest(skills=["Application Security"], scope=RetrievalScope.RESUME)
    )

    assert repo.last_filters is not None
    assert repo.last_filters["resume_eligible"] is True
    assert set(repo.last_filters["resume_visibility"]) == {
        ResumeVisibility.PUBLIC_SAFE,
        ResumeVisibility.GENERALIZE,
    }
    assert [result.evidence_key for result in response.results] == ["TT-AISEC-001"]
    assert response.results[0].safe_for_resume is True


def test_unknown_skill_is_reported_without_fabricated_match():
    service, _ = _fixture_service()
    response = service.search(
        EvidenceSearchRequest(skills=["Quantum Cryptographic Recruiting"], match_mode=MatchMode.ALL)
    )

    assert response.count == 0
    assert response.unknown_skills == ["Quantum Cryptographic Recruiting"]


def test_query_only_search_scores_lexical_coverage():
    service, _ = _fixture_service()
    response = service.search(EvidenceSearchRequest(query="AI threat modeling"))

    assert response.count == 1
    assert response.results[0].evidence_key == "TT-AISEC-001"
    assert response.results[0].score > 90
