"""FastAPI application entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from sqlalchemy import func, select

from app.api.admin import router as admin_router
from app.api.auth import router as auth_router
from app.api.interview import router as interview_router
from app.api.job import router as job_router
from app.api.resume import router as resume_router
from app.api.report import router as report_router
from app.api.user import router as user_router
from app.config import settings
from app.core.security import hash_password
from app.database.session import async_sessionmaker
from app.models.admin_user import AdminUser
from app.models.user import User


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Ensure the configured bootstrap administrator exists after migrations."""

    async with async_sessionmaker() as session:
        admin = await session.scalar(
            select(AdminUser).where(
                func.lower(AdminUser.username) == settings.admin_username.lower()
            )
        )
        if admin is None:
            session.add(
                AdminUser(
                    username=settings.admin_username,
                    password_hash=hash_password(settings.admin_password),
                )
            )
            await session.commit()

        # Restore avatar files from the database if the Docker storage volume
        # was recreated. The database copy is the durable source of truth.
        users = (await session.scalars(select(User))).all()
        storage_root = Path(settings.storage_dir).resolve()
        for user in users:
            if not user.avatar_data or not user.avatar_url:
                continue
            relative_path = user.avatar_url.removeprefix("/storage/")
            target = (storage_root / relative_path).resolve()
            if storage_root not in target.parents:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                target.write_bytes(user.avatar_data)

    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

Path(settings.storage_dir).mkdir(parents=True, exist_ok=True)
app.mount("/storage", StaticFiles(directory=settings.storage_dir), name="storage")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(job_router)
app.include_router(interview_router)
app.include_router(resume_router)
app.include_router(report_router)
app.include_router(user_router)


@app.get("/", tags=["system"])
async def read_root() -> dict[str, str]:
    """Basic liveness endpoint for the initial project scaffold."""

    return {"message": "AI Interview Agent Backend Running"}
