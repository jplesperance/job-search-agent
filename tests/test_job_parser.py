from uuid import uuid4

from job_agent.domain.jobs import RequirementImportance, WorkArrangement
from job_agent.domain.models import Skill
from job_agent.services.job_parser import DeterministicJobParser


def _skills():
    return [
        Skill(id=uuid4(), name="Application Security", aliases={"AppSec"}),
        Skill(id=uuid4(), name="Threat Modeling", aliases={"Threat Model"}),
        Skill(id=uuid4(), name="AI/LLM Security", aliases={"AI Security", "LLM Security"}),
        Skill(id=uuid4(), name="Checkmarx", aliases=set()),
    ]


def test_parser_extracts_sections_skills_years_and_arrangement():
    description = """
    This is a hybrid position.

    Requirements:
    - 8+ years of Application Security experience.
    - Strong Threat Modeling experience and AI Security knowledge.

    Preferred Qualifications:
    - Experience with Checkmarx.
    """
    parsed = DeterministicJobParser(_skills()).parse(
        "Principal Application Security Architect", description
    )

    assert parsed.role_family == "application_security"
    assert parsed.seniority == "principal"
    assert parsed.work_arrangement is WorkArrangement.HYBRID
    assert parsed.minimum_years == 8
    assert set(parsed.discovered_skills) == {
        "Application Security",
        "Threat Modeling",
        "AI/LLM Security",
        "Checkmarx",
    }
    assert parsed.requirements[0].importance is RequirementImportance.REQUIRED
    assert parsed.requirements[-1].importance is RequirementImportance.PREFERRED


def test_parser_does_not_invent_unknown_skills():
    description = """
    Requirements:
    - Must have experience with QuantumBanana Security Fabric.
    - Strong application security background.
    """
    parsed = DeterministicJobParser(_skills()).parse("Security Engineer", description)

    assert parsed.requirements[0].canonical_skills == []
    assert parsed.requirements[1].canonical_skills == ["Application Security"]


def test_parser_keeps_useful_short_taxonomy_terms_without_matching_go_noise():
    skills = [
        Skill(id=uuid4(), name="AWS", aliases=set()),
        Skill(id=uuid4(), name="Git", aliases=set()),
        Skill(id=uuid4(), name="Go", aliases=set()),
    ]
    parsed = DeterministicJobParser(skills).parse(
        "Cloud Security Engineer",
        "Qualifications:\n- Experience with AWS and Git.\n- Ability to go to customer meetings when needed.",
    )
    assert "AWS" in parsed.discovered_skills
    assert "Git" in parsed.discovered_skills
    assert "Go" not in parsed.discovered_skills


def test_senior_manager_is_detected_as_distinct_seniority():
    parser = DeterministicJobParser(_skills())
    parsed = parser.parse(
        "Senior Manager, Application Security",
        "Requirements:\n- Application Security experience",
        "San Jose, CA",
    )
    assert parsed.seniority == "senior manager"
