"""JWT claim and server-side token revocation tests."""

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.api.dependencies import get_current_user
from app.api.user import change_password
from app.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.schemas.user import PasswordChangeRequest


@pytest.mark.parametrize(
    "password",
    [
        "Short1A",
        "NOLOWERCASE1",
        "nouppercase1",
        "NoDigitsHere",
    ],
)
def test_password_change_rejects_weak_new_password(password):
    with pytest.raises(ValidationError):
        PasswordChangeRequest(
            current_password="current-password",
            new_password=password,
        )


@pytest.mark.asyncio
async def test_token_version_invalidates_existing_token(db_session, monkeypatch):
    monkeypatch.setattr(settings, "jwt_secret_key", "test-jwt-secret-with-at-least-thirty-two-characters")
    user = User(
        username="tokenuser",
        email="token@example.com",
        password_hash=hash_password("safe-password"),
        token_version=0,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    token = create_access_token(str(user.id), token_version=user.token_version)
    assert (await get_current_user(token, db_session)).id == user.id

    user.token_version += 1
    await db_session.commit()
    with pytest.raises(HTTPException) as error:
        await get_current_user(token, db_session)
    assert error.value.status_code == 401


@pytest.mark.asyncio
async def test_password_change_rotates_token_without_ending_current_session(
    db_session, monkeypatch
):
    monkeypatch.setattr(settings, "jwt_secret_key", "test-jwt-secret-with-at-least-thirty-two-characters")
    user = User(
        username="passworduser",
        email="password@example.com",
        password_hash=hash_password("old-safe-password"),
        token_version=0,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    old_token = create_access_token(str(user.id), token_version=user.token_version)
    response = await change_password(
        PasswordChangeRequest(
            current_password="old-safe-password",
            new_password="New-safe-password1",
        ),
        user,
        db_session,
    )

    assert verify_password("New-safe-password1", user.password_hash)
    assert not verify_password("old-safe-password", user.password_hash)
    with pytest.raises(HTTPException) as error:
        await get_current_user(old_token, db_session)
    assert error.value.status_code == 401
    assert (await get_current_user(response.access_token, db_session)).id == user.id
