from job_agent.domain.models import TargetingPolicy
from job_agent.services.discovery import SecurityTitlePrefilter
from job_agent.services.role_preferences import evaluate_role_preferences, heavy_coding_score


def _policy() -> TargetingPolicy:
    return TargetingPolicy(
        name="primary",
        active=True,
        target_titles=[
            "Director of Application Security",
            "Staff Product Security Engineer",
            "AI Security Architect",
        ],
        excluded_title_terms={"physical security"},
        exclude_software_engineering_roles=True,
        exclude_heavy_coding_roles=True,
    )


def test_ai_or_general_engineering_title_is_not_a_security_candidate():
    f = SecurityTitlePrefilter(_policy())
    assert not f.evaluate("Staff Software Engineer, AI Platform").accepted
    assert not f.evaluate("Strategic Projects Lead, Generative AI").accepted
    assert not f.evaluate("Director of Engineering, Physical AI").accepted


def test_explicit_software_engineering_security_titles_are_excluded():
    f = SecurityTitlePrefilter(_policy())
    assert not f.evaluate("Member of Technical Staff (Software Engineer, Security)").accepted
    assert not f.evaluate("Staff Security Software Engineer, IAM").accepted
    assert not f.evaluate("Senior Software Engineer, Security Platform").accepted


def test_non_software_security_roles_remain_eligible():
    f = SecurityTitlePrefilter(_policy())
    assert f.evaluate("Staff Product Security Engineer").accepted
    assert f.evaluate("Security Engineer, Corporate Security").accepted
    assert f.evaluate("Senior Security Engineer, Detection & Response").accepted
    assert f.evaluate("Engineering Manager, Proactive Security - Platform").accepted
    assert f.evaluate("Head of AI Security").accepted


def test_physical_security_is_excluded():
    f = SecurityTitlePrefilter(_policy())
    assert not f.evaluate("Lead Physical Security Engineer").accepted


def test_heavy_coding_requires_multiple_strong_signals_before_exclusion():
    policy = _policy()
    light = (
        "Partner with engineering teams on threat modeling. "
        "Use Python for security automation and develop security tooling where useful."
    )
    heavy = (
        "Write and maintain production code for our security platform. "
        "5+ years of software engineering experience required. "
        "Strong programming skills and hands-on coding are core to the role."
    )
    assert heavy_coding_score(light) < 4
    assert evaluate_role_preferences(title="Staff Product Security Engineer", description=light, policy=policy).accepted
    decision = evaluate_role_preferences(title="Staff Product Security Engineer", description=heavy, policy=policy)
    assert not decision.accepted
    assert "coding-heavy" in decision.rationale
