"""Registration, login, and authenticated-user API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.config import settings
from app.core.rate_limit import client_ip, enforce_rate_limit
from app.core.security import create_access_token, hash_password, verify_password
from app.database.session import get_db_session
from app.models.login_record import LoginRecord
from app.models.user import User
from app.schemas.user import TokenResponse, UserLogin, UserRegister, UserResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


# @router.post(
#     "/register",
#     response_model=UserResponse,
#     status_code=status.HTTP_201_CREATED,
# )
# async def register_user(
#     payload: UserRegister,
#     session: Annotated[AsyncSession, Depends(get_db_session)],
#     request: Request,
# ) -> UserResponse:
#     """Register a user after hashing the password with bcrypt."""
#
#     normalized_email = str(payload.email).lower()
#     normalized_username = payload.username.strip()
#     await enforce_rate_limit(
#         "auth-register", client_ip(request), limit=5, window_seconds=3600
#     )
#
#     if not normalized_username:
#         raise HTTPException(
#             status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
#             detail="账号不能为空",
#         )
#     if normalized_username.casefold() == settings.admin_username.casefold():
#         raise HTTPException(
#             status_code=status.HTTP_409_CONFLICT,
#             detail="该账号名为系统管理员保留账号",
#         )
#
#     existing_user = await session.scalar(
#         select(User).where(
#             or_(User.email == normalized_email, User.username == normalized_username)
#         )
#     )
#     if existing_user is not None:
#         detail = (
#             "邮箱已注册"
#             if existing_user.email == normalized_email
#             else "账号已注册"
#         )
#         raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)
#
#     user = User(
#         username=normalized_username,
#         email=normalized_email,
#         password_hash=hash_password(payload.password),
#     )
#     session.add(user)
#
#     try:
#         await session.commit()
#     except IntegrityError as error:
#         await session.rollback()
#         raise HTTPException(
#             status_code=status.HTTP_409_CONFLICT,
#             detail="邮箱或账号已注册",
#         ) from error
#
#     await session.refresh(user)
#     return UserResponse.model_validate(user)


@router.post("/login", response_model=TokenResponse)
async def login_user(
    payload: UserLogin,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    request: Request,
) -> TokenResponse:
    """Validate credentials and issue a signed JWT access token."""

    account = (payload.account or str(payload.email or "")).strip()
    await enforce_rate_limit(
        "auth-login-ip", client_ip(request), limit=20, window_seconds=900
    )
    await enforce_rate_limit(
        "auth-login-account", account.casefold(), limit=10, window_seconds=900
    )
    user = await session.scalar(
        select(User).where(
            or_(User.username == account, User.email == account.lower())
        )
    )

    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
        detail="账号或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    session.add(
        LoginRecord(
            user_id=user.id,
            ip_address=client_ip(request),
            user_agent=request.headers.get("user-agent", "")[:500] or None,
        )
    )
    await session.commit()

    return TokenResponse(
        access_token=create_access_token(
            subject=str(user.id), token_version=user.token_version
        )
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout_user(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    """Invalidate every access token currently issued to this user."""

    current_user.token_version += 1
    await session.commit()


@router.get("/me", response_model=UserResponse)
async def read_current_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    """Return the authenticated user's public profile."""

    return UserResponse.model_validate(current_user)
