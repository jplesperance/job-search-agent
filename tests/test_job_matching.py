from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from job_agent.domain.enums import ApprovalStatus, ResumeVisibility, VerificationStatus
from job_agent.domain.jobs import (
    JobMatchRequest,
    ParsedJobRequirement,
    RequirementImportance,
    RequirementType,
)
from job_agent.domain.models import (
    CareerProfile,
    Certification,
    EvidenceItem,
    Experience,
    JobAnalysis,
    JobOpportunity,
    Skill,
    TargetingPolicy,
)
from job_agent.domain.retrieval import EvidenceRecord
from job_agent.services.evidence_search import EvidenceSearchService
from job_agent.services.job_matching import JobMatchService


class FakeCareerRepo:
    def __init__(self, skills):
        self.skills = skills

    def get_profile(self): return None
    def list_experiences(self): return []
    def get_experience(self, experience_id): return None
    def list_skills(self): return self.skills
    def list_certifications(self): return []


class FakeEvidenceRepo:
    def __init__(self, records): self.records = records
    def get(self, identifier): return None
    def list_records(self, **filters):
        result = list(self.records)
        if filters.get("verification_statuses"):
            allowed = set(filters["verification_statuses"])
            result = [r for r in result if r.evidence.verification_status in allowed]
        if filters.get("approval_statuses"):
            allowed = set(filters["approval_statuses"])
            result = [r for r in result if r.evidence.approval_status in allowed]
        if filters.get("resume_eligible") is not None:
            result = [r for r in result if r.evidence.resume_eligible is filters["resume_eligible"]]
        if filters.get("resume_visibility"):
            allowed = set(filters["resume_visibility"])
            result = [r for r in result if r.evidence.resume_visibility in allowed]
        return result


class FakeJobRepo:
    def __init__(self, job, requirements):
        self.job = job
        self.requirements = requirements
        self.saved: JobAnalysis | None = None
        self.saved_keys = []
        self.matches = set()

    def get(self, job_id): return self.job if job_id == self.job.id else None
    def list(self, limit=100): return [self.job]
    def list_requirements(self, job_id): return self.requirements
    def replace_requirements(self, job_id, requirements):
        self.requirements = requirements
        return requirements
    def set_requirement_matches(self, job_id, matched_ordinals): self.matches = matched_ordinals
    def save_analysis(self, analysis, stable_evidence_keys=None):
        self.saved = analysis
        self.saved_keys = stable_evidence_keys or []
        return analysis
    def latest_analysis(self, job_id): return self.saved


class FakePolicyRepo:
    def __init__(self, policy): self.policy = policy
    def get(self, policy_id): return self.policy if policy_id == self.policy.id else None
    def get_active(self): return self.policy
    def list(self): return [self.policy]
    def add(self, policy, active=False): return policy
    def activate(self, policy_id): return self.policy


def _fixture():
    appsec = Skill(id=uuid4(), name="Application Security", aliases={"AppSec"})
    threat = Skill(id=uuid4(), name="Threat Modeling", aliases={"Threat Model"})
    kubernetes = Skill(id=uuid4(), name="Kubernetes", aliases={"K8s"})
    career = FakeCareerRepo([appsec, threat, kubernetes])

    exp = Experience(
        id=uuid4(), profile_id=uuid4(), employer="Example", title="Security Architect",
        start_date="2020-01-01", verification_status=VerificationStatus.USER_VERIFIED,
    )
    records = [
        EvidenceRecord(
            evidence=EvidenceItem(
                id=uuid4(), evidence_key="EV-APP-001", experience_id=exp.id,
                category="appsec", claim="Led application security reviews.",
                verification_status=VerificationStatus.USER_VERIFIED,
                approval_status=ApprovalStatus.APPROVED, resume_eligible=True,
                resume_visibility=ResumeVisibility.PUBLIC_SAFE,
            ),
            experience=exp, skills=[appsec],
        ),
        EvidenceRecord(
            evidence=EvidenceItem(
                id=uuid4(), evidence_key="EV-TM-001", experience_id=exp.id,
                category="threat_model", claim="Performed threat modeling.",
                verification_status=VerificationStatus.USER_VERIFIED,
                approval_status=ApprovalStatus.APPROVED, resume_eligible=True,
                resume_visibility=ResumeVisibility.PUBLIC_SAFE,
            ),
            experience=exp, skills=[threat],
        ),
    ]
    evidence_search = EvidenceSearchService(FakeEvidenceRepo(records), career)

    job = JobOpportunity(
        id=uuid4(), source="manual", company="Acme", title="Principal Application Security Architect",
        location="Remote", compensation_text="$220k-$280k",
        description_raw="Requirements:\n- Application Security\n- Threat Modeling\n- Kubernetes",
        discovered_at=datetime.now(timezone.utc),
    )
    requirements = [
        ParsedJobRequirement(
            ordinal=0, requirement_type=RequirementType.QUALIFICATION,
            importance=RequirementImportance.REQUIRED, text="Application Security",
            canonical_skills=["Application Security"],
        ),
        ParsedJobRequirement(
            ordinal=1, requirement_type=RequirementType.QUALIFICATION,
            importance=RequirementImportance.REQUIRED, text="Threat Modeling",
            canonical_skills=["Threat Modeling"],
        ),
        ParsedJobRequirement(
            ordinal=2, requirement_type=RequirementType.QUALIFICATION,
            importance=RequirementImportance.REQUIRED, text="Kubernetes",
            canonical_skills=["Kubernetes"],
        ),
        ParsedJobRequirement(
            ordinal=3, requirement_type=RequirementType.QUALIFICATION,
            importance=RequirementImportance.REQUIRED, text="Experience with QuantumBanana",
            canonical_skills=[],
        ),
    ]
    policy = TargetingPolicy(
        id=uuid4(), name="primary", active=True,
        target_titles=["Principal Application Security Architect"],
        target_seniority=["principal"], remote_allowed=True, hybrid_allowed=True,
        onsite_allowed=False, minimum_base_salary_usd=200000,
    )
    job_repo = FakeJobRepo(job, requirements)
    service = JobMatchService(
        job_repo=job_repo, policy_repo=FakePolicyRepo(policy), career_repo=career,
        evidence_search=evidence_search,
    )
    return service, job_repo, job


def test_match_is_grounded_in_stable_evidence_and_surfaces_gaps():
    service, repo, job = _fixture()
    result = service.analyze(job.id, JobMatchRequest())

    assert result.hard_filter_passed is True
    assert set(result.matched_evidence_keys) == {"EV-APP-001", "EV-TM-001"}
    assert "Kubernetes" in result.gaps
    assert "Experience with QuantumBanana" in result.unknowns
    assert repo.matches == {0, 1}
    assert result.total_score > 60
    assert repo.saved is not None


def test_hard_filter_rejects_disallowed_term():
    service, _, job = _fixture()
    service.policy_repo.policy.excluded_terms = {"Kubernetes"}
    result = service.analyze(job.id, JobMatchRequest())

    assert result.hard_filter_passed is False
    assert any("Excluded term present: Kubernetes" == reason for reason in result.hard_filter_reasons)


def test_remote_compensation_floor_is_a_hard_filter():
    service, _, job = _fixture()
    service.policy_repo.policy.remote_minimum_base_salary_usd = 275000
    job.compensation_text = "$240k-$270k"

    result = service.analyze(job.id, JobMatchRequest())

    assert result.hard_filter_passed is False
    assert result.location_compensation.commute_zone == "REMOTE"
    assert result.location_compensation.required_minimum_base_salary_usd == 275000
    assert any("below remote policy minimum $275,000" in reason for reason in result.hard_filter_reasons)
