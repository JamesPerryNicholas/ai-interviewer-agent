"""Business service for storing and parsing uploaded resumes."""

from datetime import datetime, timezone
from functools import partial
from pathlib import Path

import anyio
from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.resume import Resume
from app.services.pdf_service import extract_pdf_text


class ResumePdfParseError(Exception):
    """Raised when an uploaded file cannot be parsed as a PDF."""


class ResumeService:
    """Coordinate file persistence, PDF parsing, and async database writes."""

    def __init__(self, session: AsyncSession, storage_dir: str | Path | None = None) -> None:
        self.session = session
        self.storage_dir = Path(storage_dir or settings.storage_dir)

    async def create_resume(self, user_id: int, upload_file: UploadFile) -> Resume:
        """Save, parse, and persist one user's uploaded resume."""

        resume_directory = self.storage_dir / "resumes"
        await anyio.to_thread.run_sync(
            partial(resume_directory.mkdir, parents=True, exist_ok=True)
        )

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        filename = f"{user_id}_{timestamp}.pdf"
        original_filename = Path(upload_file.filename or "resume.pdf").name[:255]
        destination = resume_directory / filename
        file_content = await upload_file.read()

        if not file_content.startswith(b"%PDF-"):
            raise ResumePdfParseError("上传的文件不是 PDF")

        await anyio.to_thread.run_sync(destination.write_bytes, file_content)

        try:
            extracted_text = await anyio.to_thread.run_sync(extract_pdf_text, destination)
        except Exception as error:
            await anyio.to_thread.run_sync(partial(destination.unlink, missing_ok=True))
            raise ResumePdfParseError("无法解析上传的 PDF") from error

        resume = Resume(
            user_id=user_id,
            original_filename=original_filename,
            file_url=f"/storage/resumes/{filename}",
            content=extracted_text,
            extracted_info=None,
        )
        try:
            self.session.add(resume)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            await anyio.to_thread.run_sync(partial(destination.unlink, missing_ok=True))
            raise
        await self.session.refresh(resume)
        return resume

    async def get_latest_resume(self, user_id: int) -> Resume | None:
        """Return the most recently uploaded resume for one user."""

        result = await self.session.execute(
            select(Resume)
            .where(Resume.user_id == user_id)
            .order_by(Resume.created_at.desc(), Resume.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
