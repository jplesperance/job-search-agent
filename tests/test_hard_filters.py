from job_agent.domain.models import JobOpportunity, TargetingPolicy
from job_agent.scoring.hard_filters import evaluate_hard_filters


def test_required_and_excluded_terms() -> None:
    job = JobOpportunity(
        source="manual",
        company="Example",
        title="Lead Application Security Architect",
        description_raw="Build application security programs and threat modeling practices.",
    )
    policy = TargetingPolicy(
        name="default",
        required_terms={"application security"},
        excluded_terms={"intern"},
    )

    result = evaluate_hard_filters(job, policy)

    assert result.passed is True
    assert result.reasons == ()


def test_excluded_term_fails() -> None:
    job = JobOpportunity(
        source="manual",
        company="Example",
        title="Application Security Intern",
        description_raw="Application security internship.",
    )
    policy = TargetingPolicy(name="default", excluded_terms={"intern"})

    result = evaluate_hard_filters(job, policy)

    assert result.passed is False
