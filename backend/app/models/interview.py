"""Interview session persistence model."""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.answer import Answer
    from app.models.evaluation_report import EvaluationReport
    from app.models.job_position import JobPosition
    from app.models.message import Message
    from app.models.resume import Resume
    from app.models.user import User


class Interview(Base):
    """A user's AI interview session for one resume and job position."""

    __tablename__ = "interviews"
    __table_args__ = (
        UniqueConstraint("user_id", "start_request_id", name="uq_interviews_user_start_request"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    resume_id: Mapped[int] = mapped_column(
        ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id: Mapped[int] = mapped_column(
        ForeignKey("job_positions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default="in_progress", index=True
    )
    start_request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    completed_questions: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    current_question_index: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    total_questions: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    question_snapshot: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=False,
        server_default="[]",
    )
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="interviews")
    resume: Mapped["Resume"] = relationship(back_populates="interviews")
    job_position: Mapped["JobPosition"] = relationship(back_populates="interviews")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="interview",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )
    answers: Mapped[list["Answer"]] = relationship(
        back_populates="interview",
        cascade="all, delete-orphan",
        order_by="Answer.created_at",
    )
    evaluation_report: Mapped["EvaluationReport | None"] = relationship(
        back_populates="interview",
        uselist=False,
        cascade="all, delete-orphan",
    )
