"""User persistence model."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Integer, LargeBinary, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.interview import Interview
    from app.models.job_position import JobPosition
    from app.models.login_record import LoginRecord
    from app.models.resume import Resume


class User(Base):
    """Application user with a bcrypt password hash."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    career_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="实习求职",
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    token_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    avatar_data: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    avatar_content_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    resumes: Mapped[list["Resume"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    job_positions: Mapped[list["JobPosition"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    interviews: Mapped[list["Interview"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    login_records: Mapped[list["LoginRecord"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
