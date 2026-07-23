"""FastAPI application entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from redis.exceptions import RedisError
from sqlalchemy import func, select

from app.api.admin import router as admin_router
from app.api.auth import router as auth_router
from app.api.interview import router as interview_router
from app.api.job import router as job_router
from app.api.report import router as report_router
from app.api.resume import router as resume_router
from app.api.user import router as user_router
from app.config import settings
from app.core.distributed_lock import LockBusyError
from app.core.security import hash_password, verify_password
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
        if admin is None and settings.admin_password:
            session.add(
                AdminUser(
                    username=settings.admin_username,
                    password_hash=hash_password(settings.admin_password),
                )
            )
            await session.commit()
        elif admin is not None and (
            settings.app_env.casefold() in {"production", "prod"}
            and verify_password("admin@123", admin.password_hash)
        ):
            # Transparently rotate legacy bootstrap credentials on the first
            # production start and invalidate every previously issued token.
            admin.password_hash = hash_password(settings.admin_password)
            admin.token_version += 1
            await session.commit()

        # Restore avatar files from the database if the Docker storage volume
        # was recreated. The database copy is the durable source of truth.
        storage_root = Path(settings.storage_dir).resolve()
        users = await session.stream_scalars(
            select(User).where(User.avatar_data.is_not(None), User.avatar_url.is_not(None))
        )
        async for user in users:
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


@app.exception_handler(LockBusyError)
async def handle_lock_busy(_: Request, error: LockBusyError) -> JSONResponse:
    """Expose duplicate in-flight operations as a stable conflict response."""

    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(error)},
        headers={"Retry-After": "2"},
    )


@app.exception_handler(RedisError)
async def handle_redis_unavailable(_: Request, __: RedisError) -> JSONResponse:
    """Fail safely when a production coordination dependency is unavailable."""

    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "安全与并发控制服务暂时不可用，请稍后重试"},
    )

avatar_directory = Path(settings.storage_dir) / "avatars"
avatar_directory.mkdir(parents=True, exist_ok=True)
# Resumes are private and served only by the authenticated download endpoint.
app.mount("/storage/avatars", StaticFiles(directory=avatar_directory), name="avatars")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.parsed_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
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
