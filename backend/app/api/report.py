"""Authenticated interview report routes."""

from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.database.session import get_db_session
from app.models.user import User
from app.schemas.evaluation import EvaluationReportResponse
from app.services.evaluation_service import EvaluationResourceNotFoundError, EvaluationService
from app.services.report_pdf_service import generate_report_pdf

router = APIRouter(prefix="/api/report", tags=["report"])


@router.get("/{interview_id}", response_model=EvaluationReportResponse)
async def get_report(
    interview_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> EvaluationReportResponse:
    """Return the report for one owned interview."""

    try:
        return await EvaluationService(session).get_report(
            user_id=current_user.id,
            interview_id=interview_id,
        )
    except EvaluationResourceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.get("/{interview_id}/pdf")
async def download_report_pdf(
    interview_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> StreamingResponse:
    """Generate and download a complete PDF report."""

    try:
        _, job, report = await EvaluationService(session).get_report_context(
            user_id=current_user.id,
            interview_id=interview_id,
        )
    except EvaluationResourceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error

    pdf = generate_report_pdf(
        report=report,
        username=current_user.username,
        position=job.position,
        created_at=report.created_at,
    )
    download_name = f"{job.position}-面试评估报告.pdf"
    encoded_name = quote(download_name)
    return StreamingResponse(
        iter([pdf]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="interview-report-{interview_id}.pdf"; '
                f"filename*=UTF-8''{encoded_name}"
            ),
            "Content-Length": str(len(pdf)),
        },
    )
