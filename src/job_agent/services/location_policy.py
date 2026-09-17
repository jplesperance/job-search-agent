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


def extract_max_annual_salary(text: str | None) -> float | None:
    """Extract the largest plausible annual USD salary from a compensation string.

    This intentionally ignores percentages and values below $1,000, so bonus percentages,
    equity percentages, and hourly rates do not become false annual-salary matches.
    """
    if not text:
        return None
    values: list[float] = []
    pattern = r"\$?([0-9]{2,3}(?:,[0-9]{3})|[0-9]{5,6}|[0-9]{2,3})(\s*[kK])?"
    for raw, suffix in re.findall(pattern, text):
        value = float(raw.replace(",", ""))
        if suffix.strip().lower() == "k":
            value *= 1000
        if value >= 1000:
            values.append(value)
    return max(values) if values else None


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
    published_max = extract_max_annual_salary(job.compensation_text)

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
