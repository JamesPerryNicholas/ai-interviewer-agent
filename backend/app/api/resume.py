"""Resume upload API routes."""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.rate_limit import enforce_rate_limit
from app.database.session import get_db_session
from app.llm.deepseek import DeepSeekAPIError, DeepSeekConfigurationError
from app.models.user import User
from app.schemas.resume import ResumeAnalysisResponse, ResumeResponse
from app.services.resume_analysis_service import (
    ResumeAnalysisError,
    ResumeAnalysisService,
    ResumeNotFoundError,
)
from app.services.resume_service import (
    ResumeContentLimitError,
    ResumeFileTooLargeError,
    ResumePdfParseError,
    ResumeService,
)

router = APIRouter(prefix="/api/resume", tags=["resume"])


@router.post(
    "/upload",
    response_model=ResumeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_resume(
    file: Annotated[UploadFile, File(description="PDF resume file")],
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ResumeResponse:
    """Upload, parse, and persist a PDF resume for the current user."""

    is_pdf = (
        file.content_type == "application/pdf"
        and Path(file.filename or "").suffix.lower() == ".pdf"
    )
    if not is_pdf:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只允许上传 PDF 文件",
        )

    await enforce_rate_limit(
        "resume-upload", str(current_user.id), limit=10, window_seconds=3600
    )
    try:
        resume = await ResumeService(session).create_resume(current_user.id, file)
    except ResumeFileTooLargeError as error:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="PDF 文件不能超过 10 MB",
        ) from error
    except ResumeContentLimitError as error:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(error),
        ) from error
    except ResumePdfParseError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="上传的文件不是可读取的 PDF",
        ) from error

    return _resume_response(resume)


@router.get("/latest", response_model=ResumeResponse)
async def get_latest_resume(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ResumeResponse:
    """Return the current user's latest parsed resume for page reloads."""

    resume = await ResumeService(session).get_latest_resume(current_user.id)
    if resume is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="暂未上传简历，请先上传简历",
        )

    return _resume_response(resume)


@router.get("/{resume_id}/download")
async def download_resume(
    resume_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> FileResponse:
    """Download an owned resume through an authenticated authorization check."""

    service = ResumeService(session)
    resume = await service.get_owned_resume(resume_id, current_user.id)
    if resume is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到简历")
    path = service.resolve_file_path(resume)
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="简历文件不存在")
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=resume.original_filename,
    )


@router.post("/{resume_id}/analyze", response_model=ResumeAnalysisResponse)
async def analyze_resume(
    resume_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ResumeAnalysisResponse:
    """Analyze an owned resume with DeepSeek and persist the JSON profile."""

    await enforce_rate_limit(
        "resume-analyze", str(current_user.id), limit=8, window_seconds=3600
    )
    try:
        return await ResumeAnalysisService(session).analyze_resume(
            resume_id=resume_id,
            user_id=current_user.id,
        )
    except ResumeNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到简历",
        ) from error
    except DeepSeekConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DeepSeek API 尚未配置",
        ) from error
    except (DeepSeekAPIError, ResumeAnalysisError) as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="简历分析失败，请稍后重试",
        ) from error


def _resume_response(resume) -> ResumeResponse:
    """Hide the storage path and expose only the protected download URL."""

    response = ResumeResponse.model_validate(resume)
    return response.model_copy(
        update={"file_url": f"/api/resume/{resume.id}/download"}
    )
