"""Job position persistence model."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.interview import Interview
    from app.models.question import Question
    from app.models.user import User


class JobPosition(Base):
    """A job description saved by an authenticated user."""

    __tablename__ = "job_positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    company: Mapped[str] = mapped_column(String(150), nullable=False)
    position: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    user: Mapped["User"] = relationship(back_populates="job_positions")
    questions: Mapped[list["Question"]] = relationship(
        back_populates="job_position",
        cascade="all, delete-orphan",
    )
    interviews: Mapped[list["Interview"]] = relationship(
        back_populates="job_position",
        passive_deletes=True,
    )
