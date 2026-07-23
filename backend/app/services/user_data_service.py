"""Account erasure and private-file cleanup services."""

import logging
from functools import partial
from pathlib import Path

import anyio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.resume import Resume
from app.models.user import User

logger = logging.getLogger(__name__)


class UserDataService:
    """Delete an account transactionally, then remove its owned files."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.storage_root = Path(settings.storage_dir).resolve()

    async def delete_user(self, user: User) -> None:
        """Delete database-owned data and best-effort cleanup of private files."""

        resume_urls = list(
            await self.session.scalars(
                select(Resume.file_url).where(Resume.user_id == user.id)
            )
        )
        file_urls = resume_urls + ([user.avatar_url] if user.avatar_url else [])
        await self.session.execute(delete(User).where(User.id == user.id))
        await self.session.commit()

        for file_url in file_urls:
            path = self._safe_storage_path(file_url)
            if path is not None:
                try:
                    await anyio.to_thread.run_sync(partial(path.unlink, missing_ok=True))
                except OSError:
                    logger.exception("Unable to remove erased user file %s", path)

    def _safe_storage_path(self, file_url: str) -> Path | None:
        relative = file_url.removeprefix("/storage/")
        candidate = (self.storage_root / relative).resolve()
        if self.storage_root not in candidate.parents:
            return None
        return candidate
