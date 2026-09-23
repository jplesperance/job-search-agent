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


def test_live_style_coding_heavy_security_roles_are_excluded_but_security_manager_is_kept():
    policy = _policy()
    harvey = (
        "We are all software engineers - contributing code daily. "
        "Strong programming skills with demonstrated experience writing high-quality, production software."
    )
    perplexity_offsec = (
        "Develop and maintain custom offensive tooling, exploits, and automation. "
        "Strong programming and scripting skills in Python, Go, or similar languages."
    )
    flexport_corp = (
        "You'll spend your time writing code and shipping automation. "
        "Comfort writing real code or scripts (Python, Go, or similar)."
    )
    flexport_detection = (
        "Proficiency in Python or Go and comfort writing production-grade detection and automation code."
    )
    doordash_manager = (
        "Coach and mentor highly skilled engineers as a player-coach. "
        "Success is not measured in shipping code; it is measured in eliminating classes of vulnerabilities."
    )

    assert not evaluate_role_preferences(title="Staff Product Security Engineer", description=harvey, policy=policy).accepted
    assert not evaluate_role_preferences(title="Member of Technical Staff (Offensive Security Engineer)", description=perplexity_offsec, policy=policy).accepted
    assert not evaluate_role_preferences(title="Security Engineer, Corporate Security", description=flexport_corp, policy=policy).accepted
    assert not evaluate_role_preferences(title="Senior Security Engineer, Detection & Response", description=flexport_detection, policy=policy).accepted
    assert evaluate_role_preferences(title="Engineering Manager, Proactive Security - Pods", description=doordash_manager, policy=policy).accepted


def test_current_live_wording_for_coding_heavy_security_roles_is_rejected():
    policy = _policy()
    harvey = """
    At the same time, we are all software engineers - contributing code daily and approaching
    security with an engineering-first mindset. Strong programming skills with demonstrated
    experience writing high-quality, production software. Own and review security-critical code.
    """
    perplexity = """
    Develop and maintain custom offensive tooling, exploits, and automation. Strong programming
    and scripting skills in Python, Go, or similar languages; comfortable writing custom tooling
    and exploits.
    """
    flexport = """
    This is a security engineering role, not an IT support role. You'll spend your time writing code
    and shipping automation. Comfort writing real code or scripts (Python, Go, or similar).
    """
    detection = """
    Proficiency in at least one programming language (Python, Go, or similar) and comfort writing
    production-grade detection and automation code.
    """
    assert not evaluate_role_preferences(title="Staff Product Security Engineer", description=harvey, policy=policy).accepted
    assert not evaluate_role_preferences(title="Member of Technical Staff (Offensive Security Engineer)", description=perplexity, policy=policy).accepted
    assert not evaluate_role_preferences(title="Security Engineer, Corporate Security", description=flexport, policy=policy).accepted
    assert not evaluate_role_preferences(title="Senior Security Engineer, Detection & Response", description=detection, policy=policy).accepted
