from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from job_agent.api.dependencies import get_policy_repository
from job_agent.domain.jobs import PolicyActivationRequest, PolicySummary, TargetingPolicyCreate
from job_agent.domain.models import TargetingPolicy
from job_agent.repositories.sqlalchemy import SqlAlchemyPolicyRepository

router = APIRouter(prefix="/targeting-policies", tags=["targeting-policies"])


def _summary(policy: TargetingPolicy) -> PolicySummary:
    return PolicySummary(
        id=policy.id,
        name=policy.name,
        version=policy.version,
        active=policy.active,
        target_titles=policy.target_titles,
        target_seniority=policy.target_seniority,
        allowed_locations=policy.allowed_locations,
        remote_allowed=policy.remote_allowed,
        hybrid_allowed=policy.hybrid_allowed,
        onsite_allowed=policy.onsite_allowed,
        minimum_base_salary_usd=(float(policy.minimum_base_salary_usd) if policy.minimum_base_salary_usd is not None else None),
        required_terms=sorted(policy.required_terms),
        excluded_terms=sorted(policy.excluded_terms),
        weights=dict(policy.weights),
    )


@router.get("", response_model=list[PolicySummary])
def list_policies(
    repo: SqlAlchemyPolicyRepository = Depends(get_policy_repository),
) -> list[PolicySummary]:
    return [_summary(policy) for policy in repo.list()]


@router.post("", response_model=PolicySummary)
def create_policy(
    request: TargetingPolicyCreate,
    repo: SqlAlchemyPolicyRepository = Depends(get_policy_repository),
) -> PolicySummary:
    policy = TargetingPolicy(
        name=request.name,
        version=request.version,
        active=request.active,
        target_titles=request.target_titles,
        target_seniority=request.target_seniority,
        allowed_locations=request.allowed_locations,
        remote_allowed=request.remote_allowed,
        hybrid_allowed=request.hybrid_allowed,
        onsite_allowed=request.onsite_allowed,
        minimum_base_salary_usd=(Decimal(str(request.minimum_base_salary_usd)) if request.minimum_base_salary_usd is not None else None),
        required_terms=set(request.required_terms),
        excluded_terms=set(request.excluded_terms),
        weights=request.weights,
    )
    try:
        stored = repo.add(policy, active=request.active)
    except Exception as exc:
        raise HTTPException(status_code=409, detail=f"Could not create policy: {exc}") from exc
    return _summary(stored)


@router.post("/activate", response_model=PolicySummary)
def activate_policy(
    request: PolicyActivationRequest,
    repo: SqlAlchemyPolicyRepository = Depends(get_policy_repository),
) -> PolicySummary:
    policy = repo.activate(request.policy_id)
    if policy is None:
        raise HTTPException(status_code=404, detail="Targeting policy not found")
    # reflect active state even though the returned domain object is constructed from the row
    policy.active = True
    return _summary(policy)


@router.get("/{policy_id}", response_model=PolicySummary)
def get_policy(
    policy_id: UUID,
    repo: SqlAlchemyPolicyRepository = Depends(get_policy_repository),
) -> PolicySummary:
    policy = repo.get(policy_id)
    if policy is None:
        raise HTTPException(status_code=404, detail="Targeting policy not found")
    return _summary(policy)
