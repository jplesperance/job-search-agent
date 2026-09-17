from __future__ import annotations

import re
from dataclasses import dataclass

from job_agent.domain.jobs import LocationCompensationDecision, WorkArrangement
from job_agent.domain.models import JobOpportunity, TargetingPolicy
from job_agent.domain.retrieval import normalize_term


_GENERIC_BAY_AREA_LOCATIONS = {
    "bay area",
    "sf bay area",
    "san francisco bay area",
    "greater san francisco bay area",
    "silicon valley",
    "south bay",
    "peninsula",
    "east bay",
    "california",
    "ca",
}


def _is_ambiguous_local_location(raw_location: str | None) -> bool:
    if not raw_location:
        return True
    normalized = normalize_term(raw_location)
    if normalized in _GENERIC_BAY_AREA_LOCATIONS:
        return True
    return any(
        phrase in normalized
        for phrase in ("bay area", "silicon valley", "south bay", "east bay", "peninsula")
    )


@dataclass(frozen=True)
class LocationPolicyResult:
    decision: LocationCompensationDecision
    hard_filter_reason: str | None = None


def _salary_amount(raw: str, suffix: str | None = None) -> float | None:
    try:
        value = float(raw.replace(",", "").replace("$", "").strip())
    except ValueError:
        return None
    if suffix and suffix.strip().lower() == "k":
        value *= 1000
    return value if 10_000 <= value <= 2_000_000 else None


def extract_base_salary_range(text: str | None) -> tuple[float | None, float | None]:
    """Extract an annual base-salary range conservatively.

    Prefer salary/pay context and explicit currency ranges. This avoids treating years,
    401(k), percentages, or unrelated dollar figures as base salary.
    """
    if not text:
        return None, None

    compact = re.sub(r"\s+", " ", text).strip()
    amount = r"\$\s*([0-9]{2,3}(?:,[0-9]{3})|[0-9]{5,6}|[0-9]{2,3})\s*([kK])?"
    contextual = re.compile(
        rf"(?:base\s+(?:salary|pay)|salary\s+range|pay\s+range|annual\s+salary)"
        rf"[^\n]{{0,140}}?{amount}\s*(?:-|–|—|to)\s*{amount}",
        re.I,
    )
    explicit_range = re.compile(
        rf"{amount}\s*(?:-|–|—|to)\s*{amount}[^\n]{{0,80}}?"
        rf"(?:base\s+(?:salary|pay)|per\s+year|annually|annual)",
        re.I,
    )

    for pattern in (contextual, explicit_range):
        match = pattern.search(compact)
        if match:
            low = _salary_amount(match.group(1), match.group(2))
            high = _salary_amount(match.group(3), match.group(4))
            if low is not None and high is not None:
                return (min(low, high), max(low, high))

    # A dedicated compensation field is often just "$250k-$300k" without labels.
    # Only use this generic form for short strings to avoid mining unrelated dollar
    # amounts from a full job description.
    if len(compact) <= 180:
        generic = re.compile(rf"{amount}\s*(?:-|–|—|to)\s*{amount}", re.I).search(compact)
        if generic:
            low = _salary_amount(generic.group(1), generic.group(2))
            high = _salary_amount(generic.group(3), generic.group(4))
            if low is not None and high is not None:
                return (min(low, high), max(low, high))

    single = re.compile(
        rf"(?:base\s+(?:salary|pay)|annual\s+salary)[^\n]{{0,100}}?{amount}",
        re.I,
    ).search(compact)
    if single:
        value = _salary_amount(single.group(1), single.group(2))
        return value, value

    return None, None


def extract_max_annual_salary(text: str | None) -> float | None:
    return extract_base_salary_range(text)[1]


def _match_location(raw_location: str | None, policy: TargetingPolicy) -> tuple[str | None, str | None, float | None]:
    if not raw_location:
        return None, None, None
    normalized = normalize_term(raw_location)
    if _is_ambiguous_local_location(raw_location):
        return None, None, None

    # Match the longest location name first so a more specific configured place wins.
    candidates: list[tuple[int, str, str, float]] = []
    haystack = f" {normalized} "
    for rule in policy.location_compensation_rules:
        for location in rule.locations:
            location_norm = normalize_term(location)
            if location_norm and f" {location_norm} " in haystack:
                candidates.append(
                    (len(location_norm), location, rule.zone, float(rule.minimum_base_salary_usd))
                )
    if not candidates:
        return None, None, None
    _, city, zone, minimum = max(candidates, key=lambda item: item[0])
    return city, zone, minimum


def evaluate_location_compensation(
    job: JobOpportunity,
    policy: TargetingPolicy,
    work_arrangement: WorkArrangement,
) -> LocationPolicyResult:
    salary_source = job.compensation_text or job.description_raw
    published_max = extract_max_annual_salary(salary_source)

    if work_arrangement is WorkArrangement.REMOTE:
        minimum = (
            float(policy.remote_minimum_base_salary_usd)
            if policy.remote_minimum_base_salary_usd is not None
            else (float(policy.minimum_base_salary_usd) if policy.minimum_base_salary_usd is not None else None)
        )
        salary_passed = None if published_max is None or minimum is None else published_max >= minimum
        manual_review = published_max is None and minimum is not None
        rationale = "Fully remote role; remote compensation floor applies."
        reason = None
        if salary_passed is False:
            reason = (
                f"Published compensation maximum ${published_max:,.0f} is below remote policy minimum "
                f"${minimum:,.0f}"
            )
        elif manual_review:
            rationale += " Published base salary is unavailable; manual compensation review required."
        return LocationPolicyResult(
            decision=LocationCompensationDecision(
                raw_location=job.location,
                normalized_city=None,
                commute_zone="REMOTE",
                work_arrangement=work_arrangement,
                required_minimum_base_salary_usd=minimum,
                published_max_base_salary_usd=published_max,
                salary_passed=salary_passed,
                manual_review_required=manual_review,
                rationale=rationale,
            ),
            hard_filter_reason=reason,
        )

    city, zone, zone_minimum = _match_location(job.location, policy)
    minimum = zone_minimum
    manual_review = False
    rationale: str

    if zone is not None:
        rationale = f"Non-remote role matched commute zone {zone} via {city}."
    elif policy.location_compensation_rules and _is_ambiguous_local_location(job.location):
        # Do not reject a potentially local role just because a provider only says "Bay Area"
        # or omits the city. Preserve it for manual review and apply the global floor if set.
        minimum = float(policy.minimum_base_salary_usd) if policy.minimum_base_salary_usd is not None else None
        manual_review = True
        rationale = "Non-remote location is Bay Area-ambiguous or missing; manual location review required."
    elif policy.location_compensation_rules:
        minimum = float(policy.minimum_base_salary_usd) if policy.minimum_base_salary_usd is not None else None
        rationale = "Non-remote location is outside the configured SF Bay Area commute zones."
        decision = LocationCompensationDecision(
            raw_location=job.location,
            normalized_city=None,
            commute_zone=None,
            work_arrangement=work_arrangement,
            required_minimum_base_salary_usd=minimum,
            published_max_base_salary_usd=published_max,
            salary_passed=None if published_max is None or minimum is None else published_max >= minimum,
            manual_review_required=False,
            rationale=rationale,
        )
        return LocationPolicyResult(
            decision=decision,
            hard_filter_reason=f"Non-remote location is outside configured SF Bay Area commute zones: {job.location}",
        )
    else:
        minimum = float(policy.minimum_base_salary_usd) if policy.minimum_base_salary_usd is not None else None
        rationale = "No commute-zone rules configured; global compensation floor applies."

    salary_passed = None if published_max is None or minimum is None else published_max >= minimum
    if published_max is None and minimum is not None:
        manual_review = True
        rationale += " Published base salary is unavailable; manual compensation review required."

    reason = None
    if salary_passed is False:
        label = f"commute zone {zone}" if zone else "policy"
        reason = (
            f"Published compensation maximum ${published_max:,.0f} is below {label} minimum "
            f"${minimum:,.0f}"
        )

    return LocationPolicyResult(
        decision=LocationCompensationDecision(
            raw_location=job.location,
            normalized_city=city,
            commute_zone=zone,
            work_arrangement=work_arrangement,
            required_minimum_base_salary_usd=minimum,
            published_max_base_salary_usd=published_max,
            salary_passed=salary_passed,
            manual_review_required=manual_review,
            rationale=rationale,
        ),
        hard_filter_reason=reason,
    )
