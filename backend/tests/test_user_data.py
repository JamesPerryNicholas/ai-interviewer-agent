"""Account erasure removes database rows and persistent private files."""

import pytest
from sqlalchemy import select

from app.core.security import hash_password
from app.models.resume import Resume
from app.models.user import User
from app.services.user_data_service import UserDataService


@pytest.mark.asyncio
async def test_delete_user_removes_resume_and_avatar_files(db_session, tmp_path):
    user = User(
        username="eraseuser",
        email="erase@example.com",
        password_hash=hash_password("safe-password"),
        avatar_url="/storage/avatars/avatar.png",
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(
        Resume(
            user_id=user.id,
            original_filename="resume.pdf",
            file_url="/storage/resumes/resume.pdf",
            content="resume",
        )
    )
    await db_session.commit()

    avatar = tmp_path / "avatars" / "avatar.png"
    resume = tmp_path / "resumes" / "resume.pdf"
    avatar.parent.mkdir(parents=True)
    resume.parent.mkdir(parents=True)
    avatar.write_bytes(b"avatar")
    resume.write_bytes(b"resume")

    service = UserDataService(db_session)
    service.storage_root = tmp_path.resolve()
    await service.delete_user(user)

    assert await db_session.scalar(select(User).where(User.id == user.id)) is None
    assert not avatar.exists()
    assert not resume.exists()
