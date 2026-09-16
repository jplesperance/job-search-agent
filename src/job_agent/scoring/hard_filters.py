from dataclasses import dataclass

from job_agent.domain.models import JobOpportunity, TargetingPolicy


@dataclass(frozen=True)
class HardFilterResult:
    passed: bool
    reasons: tuple[str, ...]


def evaluate_hard_filters(job: JobOpportunity, policy: TargetingPolicy) -> HardFilterResult:
    """Apply deterministic disqualifiers before any LLM analysis."""
    haystack = f"{job.title}\n{job.location or ''}\n{job.description_raw}".lower()
    reasons: list[str] = []

    for term in sorted(policy.excluded_terms):
        if term.lower() in haystack:
            reasons.append(f"Excluded term present: {term}")

    for term in sorted(policy.required_terms):
        if term.lower() not in haystack:
            reasons.append(f"Required term missing: {term}")

    return HardFilterResult(passed=not reasons, reasons=tuple(reasons))
