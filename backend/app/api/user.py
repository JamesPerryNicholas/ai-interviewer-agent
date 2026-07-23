"""Authenticated user profile routes."""

import time
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.database.session import get_db_session
from app.models.login_record import LoginRecord
from app.models.user import User
from app.schemas.user import (
    CAREER_STATUSES,
    AccountDeleteRequest,
    LoginRecordResponse,
    PasswordChangeRequest,
    TokenResponse,
    UserResponse,
)
from app.services.user_data_service import UserDataService

router = APIRouter(prefix="/api/user", tags=["user"])


@router.get("/profile", response_model=UserResponse)
async def get_profile(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    """Return the public profile for the authenticated user."""

    return UserResponse.model_validate(current_user)


@router.patch("/profile", response_model=UserResponse)
async def update_profile(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    display_name: Annotated[str | None, Form()] = None,
    career_status: Annotated[str | None, Form()] = None,
    avatar: Annotated[UploadFile | None, File()] = None,
) -> UserResponse:
    """Update the display name, career status, and optional avatar."""

    previous_avatar: Path | None = None
    new_avatar: Path | None = None

    if display_name is not None:
        normalized_name = display_name.strip()
        if not normalized_name:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="展示名称不能为空")
        if len(normalized_name) > 50:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="展示名称不能超过 50 个字符")
        current_user.display_name = normalized_name

    if career_status is not None:
        normalized_status = career_status.strip()
        if normalized_status not in CAREER_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="请选择有效的求职状态",
            )
        current_user.career_status = normalized_status

    if avatar is not None and avatar.filename:
        allowed_types = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
        extension = allowed_types.get(avatar.content_type or "")
        if extension is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="头像仅支持 JPG、PNG 或 WEBP 格式")

        content = await avatar.read(settings.max_avatar_upload_bytes + 1)
        if len(content) > settings.max_avatar_upload_bytes:
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="头像大小不能超过 5 MB")
        if not _has_valid_image_signature(content, avatar.content_type or ""):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="头像文件内容与格式不匹配")

        avatar_directory = Path(settings.storage_dir) / "avatars"
        avatar_directory.mkdir(parents=True, exist_ok=True)
        filename = f"{current_user.id}_{time.time_ns()}{extension}"
        new_avatar = avatar_directory / filename
        new_avatar.write_bytes(content)
        previous_avatar = _safe_avatar_path(current_user.avatar_url)
        current_user.avatar_url = f"/storage/avatars/{filename}"
        current_user.avatar_data = content
        current_user.avatar_content_type = avatar.content_type

    try:
        await session.commit()
    except Exception:
        await session.rollback()
        if new_avatar is not None:
            new_avatar.unlink(missing_ok=True)
        raise
    await session.refresh(current_user)
    if avatar is not None and avatar.filename and previous_avatar is not None:
        previous_avatar.unlink(missing_ok=True)
    return UserResponse.model_validate(current_user)


@router.patch("/password", response_model=TokenResponse)
async def change_password(
    payload: PasswordChangeRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TokenResponse:
    """Change the password and rotate the current device's access token."""

    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前密码不正确")
    if payload.current_password == payload.new_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="新密码不能与当前密码相同")

    current_user.password_hash = hash_password(payload.new_password)
    current_user.token_version += 1
    await session.commit()
    return TokenResponse(
        access_token=create_access_token(
            subject=str(current_user.id),
            token_version=current_user.token_version,
        )
    )


@router.delete("/account", status_code=status.HTTP_204_NO_CONTENT)
async def delete_own_account(
    payload: AccountDeleteRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    """Permanently erase the current user's account, data, and stored files."""

    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前密码不正确")
    await UserDataService(session).delete_user(current_user)


@router.get("/login-records", response_model=list[LoginRecordResponse])
async def list_login_records(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[LoginRecordResponse]:
    """Return the latest successful logins for the current user."""

    result = await session.scalars(
        select(LoginRecord)
        .where(LoginRecord.user_id == current_user.id)
        .order_by(desc(LoginRecord.login_at), desc(LoginRecord.id))
        .limit(5)
    )
    return [LoginRecordResponse.model_validate(record) for record in result]


def _safe_avatar_path(avatar_url: str | None) -> Path | None:
    if not avatar_url:
        return None
    root = Path(settings.storage_dir).resolve()
    candidate = (root / avatar_url.removeprefix("/storage/")).resolve()
    return candidate if root in candidate.parents else None


def _has_valid_image_signature(content: bytes, content_type: str) -> bool:
    signatures = {
        "image/jpeg": content.startswith(b"\xff\xd8\xff"),
        "image/png": content.startswith(b"\x89PNG\r\n\x1a\n"),
        "image/webp": len(content) >= 12
        and content.startswith(b"RIFF")
        and content[8:12] == b"WEBP",
    }
    return signatures.get(content_type, False)
