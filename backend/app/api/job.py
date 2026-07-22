"""Authenticated job position routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.database.session import get_db_session
from app.models.interview import Interview
from app.models.job_position import JobPosition
from app.models.user import User
from app.schemas.job import JobPositionCreate, JobPositionResponse


router = APIRouter(prefix="/api/job", tags=["job"])


@router.post("/create", response_model=JobPositionResponse, status_code=status.HTTP_201_CREATED)
async def create_job_position(
    payload: JobPositionCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> JobPositionResponse:
    """Save a job description for the authenticated user."""

    job_position = JobPosition(
        user_id=current_user.id,
        company=payload.company.strip(),
        position=payload.position.strip(),
        description=payload.description.strip(),
    )
    session.add(job_position)
    await session.commit()
    await session.refresh(job_position)
    return JobPositionResponse.model_validate(job_position)


@router.get("/list", response_model=list[JobPositionResponse])
async def list_job_positions(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[JobPositionResponse]:
    """List only the authenticated user's saved job descriptions."""

    result = await session.execute(
        select(JobPosition)
        .where(JobPosition.user_id == current_user.id)
        .order_by(JobPosition.created_at.desc(), JobPosition.id.desc())
    )
    return [JobPositionResponse.model_validate(job) for job in result.scalars().all()]


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job_position(
    job_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    """Delete one owned job that has not been used for an interview."""

    job_position = await session.scalar(
        select(JobPosition).where(
            JobPosition.id == job_id,
            JobPosition.user_id == current_user.id,
        )
    )
    if job_position is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="岗位不存在")

    interview_count = await session.scalar(
        select(func.count(Interview.id)).where(Interview.job_id == job_id)
    )
    if interview_count:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="该岗位已经关联面试记录，不能删除",
        )

    await session.delete(job_position)
    await session.commit()
