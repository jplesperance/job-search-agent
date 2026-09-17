from __future__ import annotations

import json
from pathlib import Path

from job_agent.domain.jobs import TargetingPolicyCreate, WorkArrangement
from job_agent.domain.models import JobOpportunity, TargetingPolicy
from job_agent.services.location_policy import evaluate_location_compensation


def _policy() -> TargetingPolicy:
    payload = TargetingPolicyCreate.model_validate_json(
        Path("data/examples/targeting_policy.example.json").read_text()
    )
    return TargetingPolicy(
        name=payload.name,
        version=payload.version,
        active=payload.active,
        target_titles=payload.target_titles,
        target_seniority=payload.target_seniority,
        allowed_locations=payload.allowed_locations,
        remote_allowed=payload.remote_allowed,
        hybrid_allowed=payload.hybrid_allowed,
        onsite_allowed=payload.onsite_allowed,
        minimum_base_salary_usd=payload.minimum_base_salary_usd,
        remote_minimum_base_salary_usd=payload.remote_minimum_base_salary_usd,
        location_compensation_rules=payload.location_compensation_rules,
        required_terms=set(payload.required_terms),
        excluded_terms=set(payload.excluded_terms),
        weights=payload.weights,
    )


def _job(location: str | None, compensation: str | None) -> JobOpportunity:
    return JobOpportunity(
        source="manual",
        company="Example",
        title="Security Director",
        location=location,
        compensation_text=compensation,
        description_raw="A sufficiently long security leadership job description.",
    )


def test_remote_uses_275k_floor_even_with_sf_location():
    result = evaluate_location_compensation(
        _job("San Francisco, CA - Remote", "$250k-$280k base"),
        _policy(),
        WorkArrangement.REMOTE,
    )
    assert result.hard_filter_reason is None
    assert result.decision.commute_zone == "REMOTE"
    assert result.decision.required_minimum_base_salary_usd == 275000
    assert result.decision.salary_passed is True


def test_remote_below_floor_fails():
    result = evaluate_location_compensation(
        _job("Remote - US", "$240k-$270k"), _policy(), WorkArrangement.REMOTE
    )
    assert result.decision.salary_passed is False
    assert "$275,000" in result.hard_filter_reason


def test_zone_a_san_jose_floor():
    result = evaluate_location_compensation(
        _job("San Jose, CA", "$250,000-$274,000"), _policy(), WorkArrangement.HYBRID
    )
    assert result.decision.normalized_city == "San Jose"
    assert result.decision.commute_zone == "A"
    assert result.decision.required_minimum_base_salary_usd == 275000
    assert result.decision.salary_passed is False


def test_zone_b_redwood_city_floor():
    result = evaluate_location_compensation(
        _job("Redwood City, California", "$275k-$305k"), _policy(), WorkArrangement.ONSITE
    )
    assert result.decision.commute_zone == "B"
    assert result.decision.required_minimum_base_salary_usd == 300000
    assert result.decision.salary_passed is True


def test_zone_c_san_francisco_floor():
    result = evaluate_location_compensation(
        _job("San Francisco, CA", "$290k-$320k"), _policy(), WorkArrangement.HYBRID
    )
    assert result.decision.commute_zone == "C"
    assert result.decision.required_minimum_base_salary_usd == 325000
    assert result.decision.salary_passed is False


def test_generic_bay_area_requires_manual_review_not_rejection():
    result = evaluate_location_compensation(
        _job("San Francisco Bay Area", "$280k-$310k"), _policy(), WorkArrangement.HYBRID
    )
    assert result.hard_filter_reason is None
    assert result.decision.commute_zone is None
    assert result.decision.manual_review_required is True
    assert result.decision.required_minimum_base_salary_usd == 275000


def test_missing_salary_requires_manual_review():
    result = evaluate_location_compensation(
        _job("Palo Alto, CA", None), _policy(), WorkArrangement.HYBRID
    )
    assert result.hard_filter_reason is None
    assert result.decision.commute_zone == "A"
    assert result.decision.salary_passed is None
    assert result.decision.manual_review_required is True


def test_example_policy_is_valid_json_and_model():
    path = Path("data/examples/targeting_policy.example.json")
    json.loads(path.read_text())
    policy = TargetingPolicyCreate.model_validate_json(path.read_text())
    assert policy.remote_minimum_base_salary_usd == 275000
    assert {rule.zone for rule in policy.location_compensation_rules} == {"A", "B", "C"}


def test_non_remote_outside_bay_area_is_rejected():
    result = evaluate_location_compensation(
        _job("Los Angeles, CA", "$350k-$400k"), _policy(), WorkArrangement.HYBRID
    )
    assert result.decision.commute_zone is None
    assert result.decision.manual_review_required is False
    assert "outside configured SF Bay Area commute zones" in result.hard_filter_reason
