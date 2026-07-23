"""Reusable FastAPI dependencies for authenticated requests."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.session import get_db_session
from app.models.admin_user import AdminUser
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> User:
    """Decode a Bearer JWT and return the corresponding database user."""

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="登录凭证无效，请重新登录",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
        )
        if payload.get("token_type") != "user":
            raise credentials_exception
        subject = payload.get("sub")
        if subject is None:
            raise credentials_exception
        user_id = int(subject)
    except (JWTError, TypeError, ValueError) as error:
        raise credentials_exception from error

    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception
    if payload.get("ver") != user.token_version:
        raise credentials_exception

    return user


async def get_current_admin(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AdminUser:
    """Decode an admin JWT and return the active administrator."""

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="管理员身份验证失败",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
        )
        if payload.get("token_type") != "admin":
            raise credentials_exception
        subject = payload.get("sub")
        if subject is None:
            raise credentials_exception
        admin_id = int(subject)
    except (JWTError, TypeError, ValueError) as error:
        raise credentials_exception from error

    admin = await session.scalar(
        select(AdminUser).where(AdminUser.id == admin_id, AdminUser.is_active.is_(True))
    )
    if admin is None:
        raise credentials_exception
    if payload.get("ver") != admin.token_version:
        raise credentials_exception
    return admin
