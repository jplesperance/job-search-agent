from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from job_agent.domain.jobs import JobMatchRequest, TargetingPolicyCreate
from job_agent.domain.models import EvidenceItem, Experience, JobOpportunity, Skill, TargetingPolicy
from job_agent.domain.retrieval import EvidenceRecord
from job_agent.services.evidence_search import EvidenceSearchService
from job_agent.services.job_matching import JobMatchService
from job_agent.services.job_parser import DeterministicJobParser
from job_agent.services.location_policy import extract_base_salary_range


BETTERHELP_JD = """
BetterHelp is seeking a highly technical Head of Security Engineering to lead our security strategy with a strong emphasis on offensive security and attacker mindset.

Responsibilities:
- Direct and evolve the company’s red team capabilities, including penetration testing, code review, and vulnerability discovery
- Strengthen processes around vulnerability management, detection, and response

Requirements:
- 5+ years of security leadership experience
- 10+ years of experience in security engineering
- Strong background in offensive security (red team, penetration testing, or bug bounty)
- Deep understanding of how modern systems are attacked, and how to defend against them
- Experience working across or leading Red team, Blue team / SecOps, or Application Security
- Experience setting strategy, managing roadmaps, and delivering measurable security outcomes across multiple teams.
- Ability to operate both strategically and hands-on
- Experience working in fast-paced environments with frequent releases
- Strong communication skills with both technical and non-technical stakeholders

Benefits:
- Remote work with regular in-person bonding experiences sponsored by the company
- Competitive compensation
- Holistic perks program (including free therapy, employee wellness, and more)
- Excellent health, dental, and vision coverage
- 401k benefits with employer matching contribution
- Any piece of hardware or software that will make you happy and productive

Preferred Qualifications:
- Experience with AI/ML security or emerging attack vectors
- Experience working with PHI/PII
- Experience operating in environments with high regulatory, privacy, or customer trust requirements.
- Experience building and operating security programs for large-scale cloud, distributed systems, or consumer platforms.
- Experience partnering with GRC teams

The base salary range for this position is $250,000 - $300,000. In addition to the base salary, this position is eligible for a performance bonus.
"""


def _load_seed():
    return json.loads(Path("data/knowledge_base/v1/postgres_compat_seed.json").read_text())


def _seed_models():
    seed = _load_seed()
    skills = [
        Skill(id=UUID(s["id"]), name=s["name"], category=s.get("category"), aliases=set(s.get("aliases", [])))
        for s in seed["skills"]
    ]
    experiences = [
        Experience(
            id=UUID(e["id"]), canonical_key=e.get("canonical_key"), profile_id=UUID(e["profile_id"]),
            employer=e["employer"], title=e["title"], start_date=e["start_date"], end_date=e.get("end_date"),
            location=e.get("location"), description=e.get("description"), verification_status=e.get("verification_status"),
        )
        for e in seed["experiences"]
    ]
    experience_by_id = {e.id: e for e in experiences}
    skill_by_id = {s.id: s for s in skills}
    skills_by_evidence: dict[UUID, list[Skill]] = {}
    for mapping in seed["evidence_skills"]:
        skills_by_evidence.setdefault(UUID(mapping["evidence_id"]), []).append(skill_by_id[UUID(mapping["skill_id"])])

    records = []
    for e in seed["evidence_items"]:
        evidence = EvidenceItem(
            id=UUID(e["id"]), evidence_key=e.get("evidence_key"),
            experience_id=UUID(e["experience_id"]) if e.get("experience_id") else None,
            category=e["category"], claim=e["claim"], context=e.get("context"), metric=e.get("metric"),
            provenance=e.get("provenance"), verification_status=e.get("verification_status"),
            approval_status=e.get("approval_status", "approved"), resume_eligible=e.get("resume_eligible", False),
            resume_visibility=e.get("resume_visibility"), tags=set(e.get("tags", [])),
        )
        records.append(EvidenceRecord(
            evidence=evidence,
            experience=experience_by_id.get(evidence.experience_id),
            skills=skills_by_evidence.get(evidence.id, []),
        ))
    return skills, experiences, records


class CareerRepo:
    def __init__(self, skills, experiences):
        self.skills = skills
        self.experiences = experiences
    def get_profile(self): return None
    def list_experiences(self): return self.experiences
    def get_experience(self, experience_id): return next((x for x in self.experiences if x.id == experience_id), None)
    def list_skills(self): return self.skills
    def list_certifications(self): return []


class EvidenceRepo:
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


class JobRepo:
    def __init__(self, job): self.job = job; self.requirements = []; self.saved = None
    def get(self, job_id): return self.job if self.job.id == job_id else None
    def replace_requirements(self, job_id, requirements): self.requirements = requirements; return requirements
    def list_requirements(self, job_id): return self.requirements
    def set_requirement_matches(self, job_id, ordinals): pass
    def save_analysis(self, analysis, **kwargs): self.saved = (analysis, kwargs); return analysis


class PolicyRepo:
    def __init__(self, policy): self.policy = policy
    def get(self, policy_id): return self.policy
    def get_active(self): return self.policy


def _policy() -> TargetingPolicy:
    payload = TargetingPolicyCreate.model_validate_json(Path("data/examples/targeting_policy.example.json").read_text())
    return TargetingPolicy(
        name=payload.name, version=payload.version, active=True, target_titles=payload.target_titles,
        target_seniority=payload.target_seniority, allowed_locations=payload.allowed_locations,
        remote_allowed=payload.remote_allowed, hybrid_allowed=payload.hybrid_allowed, onsite_allowed=payload.onsite_allowed,
        minimum_base_salary_usd=payload.minimum_base_salary_usd,
        remote_minimum_base_salary_usd=payload.remote_minimum_base_salary_usd,
        location_compensation_rules=payload.location_compensation_rules,
        required_terms=set(payload.required_terms), excluded_terms=set(payload.excluded_terms), weights=payload.weights,
    )


def test_betterhelp_parser_excludes_benefits_and_maps_key_domains():
    skills, _, _ = _seed_models()
    parsed = DeterministicJobParser(skills).parse(
        "Head of Security Engineering", BETTERHELP_JD, "Mountain View (Hybrid)"
    )
    texts = [r.text for r in parsed.requirements]
    assert not any(text == "Benefits" or "401k" in text or "free therapy" in text for text in texts)
    by_text = {r.text: r for r in parsed.requirements}
    assert by_text["Experience with AI/ML security or emerging attack vectors"].canonical_skills == ["AI/LLM Security"]
    assert set(by_text["Experience working with PHI/PII"].canonical_skills) == {"Healthcare Security", "Privacy Engineering", "Data Security"}
    assert set(by_text["Experience partnering with GRC teams"].canonical_skills) == {"Security Governance", "Risk Management", "Compliance"}
    assert by_text["5+ years of security leadership experience"].requirement_kind.value == "leadership_years"
    assert by_text["10+ years of experience in security engineering"].requirement_kind.value == "experience_years"


def test_full_jd_salary_extraction_ignores_years_and_401k():
    assert extract_base_salary_range(BETTERHELP_JD) == (250000.0, 300000.0)
    assert extract_base_salary_range("Benefits 2025; 401k matching") == (None, None)


def test_betterhelp_regression_is_not_a_false_100_and_salary_passes_zone_a():
    skills, experiences, records = _seed_models()
    career = CareerRepo(skills, experiences)
    job = JobOpportunity(
        source="manual", company="BetterHelp", title="Head of Security Engineering",
        location="Mountain View (Hybrid)", compensation_text=None, description_raw=BETTERHELP_JD,
        discovered_at=datetime.now(timezone.utc),
    )
    job_repo = JobRepo(job)
    service = JobMatchService(
        job_repo=job_repo, policy_repo=PolicyRepo(_policy()), career_repo=career,
        evidence_search=EvidenceSearchService(EvidenceRepo(records), career),
    )
    result = service.analyze(job.id, JobMatchRequest())

    assert result.hard_filter_passed is True
    assert result.location_compensation.commute_zone == "A"
    assert result.location_compensation.published_max_base_salary_usd == 300000
    assert result.location_compensation.salary_passed is True
    assert result.total_score < 100
    assert result.components["requirements"] < 100
    assert result.confidence.required_total == 9
    assert result.confidence.required_recognized == 9
    assert "Strong background in offensive security (red team, penetration testing, or bug bounty)" in result.gaps
    assert not any("401k" in item for item in result.unknowns)
    assert not any("Benefits" == item for item in result.unknowns)


def test_tenure_requirements_use_threshold_proofs_not_decimal_year_claims():
    skills, experiences, records = _seed_models()
    career = CareerRepo(skills, experiences)
    job = JobOpportunity(
        source="manual", company="BetterHelp", title="Head of Security Engineering",
        location="Mountain View (Hybrid)", compensation_text=None, description_raw=BETTERHELP_JD,
        discovered_at=datetime.now(timezone.utc),
    )
    service = JobMatchService(
        job_repo=JobRepo(job), policy_repo=PolicyRepo(_policy()), career_repo=career,
        evidence_search=EvidenceSearchService(EvidenceRepo(records), career),
    )
    result = service.analyze(job.id, JobMatchRequest())
    by_text = {item.requirement: item for item in result.requirement_coverage}

    leadership = by_text["5+ years of security leadership experience"]
    engineering = by_text["10+ years of experience in security engineering"]

    for item, minimum in ((leadership, 5), (engineering, 10)):
        assert item.matched is True
        assert item.minimum_years == minimum
        assert item.tenure_threshold_met is True
        assert item.qualifying_experience_keys
        assert "exact specialized tenure is intentionally not asserted" in item.rationale
        assert "Estimated " not in item.rationale
        assert ".8 years" not in item.rationale
        assert ".2 years" not in item.rationale
