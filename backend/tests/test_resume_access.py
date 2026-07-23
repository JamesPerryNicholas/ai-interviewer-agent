"""Private resume ownership and path traversal tests."""

import pytest

from app.core.security import hash_password
from app.models.resume import Resume
from app.models.user import User
from app.services.resume_service import ResumePdfParseError, ResumeService


@pytest.mark.asyncio
async def test_resume_lookup_enforces_owner(db_session, tmp_path):
    owner = User(
        username="owner",
        email="owner@example.com",
        password_hash=hash_password("safe-password"),
    )
    stranger = User(
        username="stranger",
        email="stranger@example.com",
        password_hash=hash_password("safe-password"),
    )
    db_session.add_all([owner, stranger])
    await db_session.flush()
    resume = Resume(
        user_id=owner.id,
        original_filename="resume.pdf",
        file_url="/storage/resumes/resume.pdf",
        content="resume",
    )
    db_session.add(resume)
    await db_session.commit()

    service = ResumeService(db_session, tmp_path)
    assert await service.get_owned_resume(resume.id, owner.id) is not None
    assert await service.get_owned_resume(resume.id, stranger.id) is None


def test_resume_path_rejects_traversal(tmp_path):
    service = ResumeService(None, tmp_path)  # type: ignore[arg-type]
    resume = Resume(
        user_id=1,
        original_filename="resume.pdf",
        file_url="/storage/../../outside.pdf",
        content="resume",
    )
    with pytest.raises(ResumePdfParseError):
        service.resolve_file_path(resume)
