"""Administrator authentication, usage dashboard, and account management APIs."""

import math
import re
import secrets
import string
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_admin
from app.config import settings
from app.core.rate_limit import client_ip, enforce_rate_limit
from app.core.security import create_access_token, hash_password, verify_password
from app.database.session import get_db_session
from app.models.admin_user import AdminUser
from app.models.llm_usage import LLMUsage
from app.models.user import User
from app.schemas.admin import (
    AdminCreatedUserResponse,
    AdminCreateUserRequest,
    AdminLoginRequest,
    AdminResponse,
    AdminTokenResponse,
    AdminUserListItem,
    UsageDailyPoint,
    UsageFeaturePoint,
    UsageRecordResponse,
    UsageSummaryResponse,
)
from app.services.user_data_service import UserDataService

router = APIRouter(prefix="/api/admin", tags=["admin"])
ACCOUNT_PATTERN = re.compile(r"^[A-Za-z]+$")


@router.post("/auth/login", response_model=AdminTokenResponse)
async def admin_login(
    payload: AdminLoginRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    request: Request,
) -> AdminTokenResponse:
    """Authenticate an administrator with the separate admin account table."""

    await enforce_rate_limit(
        "admin-login-ip", client_ip(request), limit=10, window_seconds=900
    )
    await enforce_rate_limit(
        "admin-login-account", payload.username.casefold(), limit=6, window_seconds=900
    )
    admin = await session.scalar(
        select(AdminUser).where(func.lower(AdminUser.username) == payload.username.strip().lower())
    )
    if admin is None or not admin.is_active or not verify_password(payload.password, admin.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="管理员账号或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return AdminTokenResponse(
        access_token=create_access_token(
            str(admin.id), token_type="admin", token_version=admin.token_version
        ),
        admin=AdminResponse.model_validate(admin),
    )


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def admin_logout(
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    """Invalidate all active tokens issued to the current administrator."""

    current_admin.token_version += 1
    await session.commit()


@router.get("/me", response_model=AdminResponse)
async def admin_me(
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
) -> AdminResponse:
    return AdminResponse.model_validate(current_admin)


@router.get("/users", response_model=list[AdminUserListItem])
async def list_created_users(
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[AdminUserListItem]:
    """List regular user accounts without exposing password hashes."""

    result = await session.execute(
        select(User)
        .where(func.lower(User.username) != settings.admin_username.casefold())
        .order_by(User.created_at.desc(), User.id.desc())
        .limit(50)
    )
    return [
        AdminUserListItem(
            id=user.id,
            username=user.username,
            email=user.email,
            created_at=user.created_at,
        )
        for user in result.scalars().all()
    ]


@router.post("/users", response_model=AdminCreatedUserResponse, status_code=status.HTTP_201_CREATED)
async def create_user_account(
    payload: AdminCreateUserRequest,
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AdminCreatedUserResponse:
    """Create a regular user; generated usernames contain English letters only."""

    username = payload.username.strip() if payload.username else await _generate_unique_username(session)
    if not ACCOUNT_PATTERN.fullmatch(username):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="账号名只能包含英文字母")
    if username.casefold() == settings.admin_username.casefold():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="admin 是系统管理员保留账号，不能作为普通用户账号")
    if await _user_exists(session, username):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="账号名已存在，请更换后重试")

    password = payload.password or _generate_password()
    # Use a reserved but valid example domain so Pydantic EmailStr accepts
    # the internal address returned by the user profile endpoint.
    email = f"{username.lower()}.{secrets.token_hex(4)}@ai-interviewer.example.com"
    user = User(username=username, email=email, password_hash=hash_password(password))
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return AdminCreatedUserResponse(
        id=user.id,
        username=user.username,
        password=password,
        email=user.email,
        created_at=user.created_at,
    )


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_account(
    user_id: int,
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    """Delete a regular user account and its database-owned interview data.

    Administrator identities live in ``admin_users`` and are never returned by
    the regular user list, so this endpoint cannot delete the logged-in admin.
    The check is intentionally performed against the User table only.
    """

    user = await session.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户账号不存在")
    if user.username.casefold() == settings.admin_username.casefold():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="系统管理员账号不可删除")

    await UserDataService(session).delete_user(user)


@router.get("/usage/summary", response_model=UsageSummaryResponse)
async def usage_summary(
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    days: int = Query(default=7, ge=1, le=31),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
) -> UsageSummaryResponse:
    """Return token, feature, and latency aggregates for the admin dashboard."""

    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days - 1)
    result = await session.execute(
        select(LLMUsage)
        .where(LLMUsage.created_at >= start)
        .order_by(LLMUsage.created_at.desc(), LLMUsage.id.desc())
    )
    records = list(result.scalars().all())

    daily = defaultdict(lambda: [0, 0, 0])
    by_feature = defaultdict(lambda: [0, 0])
    latencies: list[int] = []
    for record in records:
        date_key = record.created_at.astimezone().date().isoformat()
        daily[date_key][0] += record.total_tokens
        daily[date_key][1] += record.prompt_tokens
        daily[date_key][2] += record.completion_tokens
        by_feature[record.feature][0] += record.total_tokens
        by_feature[record.feature][1] += 1
        latencies.append(record.latency_ms)

    daily_points = []
    for offset in range(days - 1, -1, -1):
        date_key = (now - timedelta(days=offset)).astimezone().date().isoformat()
        values = daily[date_key]
        daily_points.append(
            UsageDailyPoint(
                date=date_key,
                total_tokens=values[0],
                prompt_tokens=values[1],
                completion_tokens=values[2],
            )
        )

    today = now.astimezone().date().isoformat()
    recent_total = len(records)
    recent_start = (page - 1) * page_size
    recent_records = records[recent_start : recent_start + page_size]
    total_tokens = sum(record.total_tokens for record in records)
    prompt_tokens = sum(record.prompt_tokens for record in records)
    completion_tokens = sum(record.completion_tokens for record in records)
    sorted_latencies = sorted(latencies)
    return UsageSummaryResponse(
        range_days=days,
        budget_tokens=settings.admin_budget_tokens,
        total_tokens=total_tokens,
        total_calls=len(records),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        today_tokens=daily[today][0],
        daily=[point for point in daily_points],
        by_feature=[
            UsageFeaturePoint(feature=feature, total_tokens=values[0], calls=values[1])
            for feature, values in sorted(by_feature.items(), key=lambda item: item[1][0], reverse=True)
        ],
        p50_latency_ms=_percentile(sorted_latencies, 0.50),
        p90_latency_ms=_percentile(sorted_latencies, 0.90),
        p99_latency_ms=_percentile(sorted_latencies, 0.99),
        average_latency_ms=round(sum(latencies) / len(latencies)) if latencies else 0,
        recent=[
            UsageRecordResponse.model_validate(record)
            for record in recent_records
        ],
        recent_total=recent_total,
        recent_page=page,
        recent_page_size=page_size,
    )


async def _user_exists(session: AsyncSession, username: str) -> bool:
    return bool(
        await session.scalar(
            select(User.id).where(func.lower(User.username) == username.lower())
        )
    )


async def _generate_unique_username(session: AsyncSession) -> str:
    alphabet = string.ascii_lowercase
    for _ in range(20):
        candidate = "".join(secrets.choice(alphabet) for _ in range(10))
        if not await _user_exists(session, candidate):
            return candidate
    raise HTTPException(status_code=500, detail="暂时无法生成唯一账号，请稍后重试")


def _generate_password() -> str:
    alphabet = string.ascii_letters + string.digits + "@#$%"
    return "".join(secrets.choice(alphabet) for _ in range(12))


def _percentile(values: list[int], percentile: float) -> int:
    if not values:
        return 0
    index = max(0, min(len(values) - 1, math.ceil(percentile * len(values)) - 1))
    return values[index]
