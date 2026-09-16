from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from job_agent.api.dependencies import get_career_repository
from job_agent.domain.models import CareerProfile, Certification, Experience, Skill
from job_agent.repositories.sqlalchemy import SqlAlchemyCareerRepository

router = APIRouter(tags=["career"])


@router.get("/profile", response_model=CareerProfile)
def get_profile(
    repo: SqlAlchemyCareerRepository = Depends(get_career_repository),
) -> CareerProfile:
    profile = repo.get_profile()
    if profile is None:
        raise HTTPException(status_code=404, detail="Career profile not found")
    return profile


@router.get("/experiences", response_model=list[Experience])
def list_experiences(
    repo: SqlAlchemyCareerRepository = Depends(get_career_repository),
) -> list[Experience]:
    return repo.list_experiences()


@router.get("/experiences/{experience_id}", response_model=Experience)
def get_experience(
    experience_id: UUID,
    repo: SqlAlchemyCareerRepository = Depends(get_career_repository),
) -> Experience:
    experience = repo.get_experience(experience_id)
    if experience is None:
        raise HTTPException(status_code=404, detail="Experience not found")
    return experience


@router.get("/skills", response_model=list[Skill])
def list_skills(
    repo: SqlAlchemyCareerRepository = Depends(get_career_repository),
) -> list[Skill]:
    return repo.list_skills()


@router.get("/certifications", response_model=list[Certification])
def list_certifications(
    repo: SqlAlchemyCareerRepository = Depends(get_career_repository),
) -> list[Certification]:
    return repo.list_certifications()
