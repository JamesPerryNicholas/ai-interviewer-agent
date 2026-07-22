"""create interviews and messages

Revision ID: c7b2d4e91f10
Revises: a16fae606e15
Create Date: 2026-07-20

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c7b2d4e91f10"
down_revision: Union[str, Sequence[str], None] = "a16fae606e15"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create interview sessions and their chat messages."""

    op.create_table(
        "interviews",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("resume_id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=30),
            server_default=sa.text("'in_progress'"),
            nullable=False,
        ),
        sa.Column("start_time", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["job_id"], ["job_positions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resume_id"], ["resumes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_interviews_user_id", "interviews", ["user_id"], unique=False)
    op.create_index("ix_interviews_resume_id", "interviews", ["resume_id"], unique=False)
    op.create_index("ix_interviews_job_id", "interviews", ["job_id"], unique=False)
    op.create_index("ix_interviews_status", "interviews", ["status"], unique=False)

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("interview_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["interview_id"], ["interviews.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_messages_interview_id", "messages", ["interview_id"], unique=False)
    op.create_index("ix_messages_created_at", "messages", ["created_at"], unique=False)


def downgrade() -> None:
    """Drop messages and interview sessions."""

    op.drop_index("ix_messages_created_at", table_name="messages")
    op.drop_index("ix_messages_interview_id", table_name="messages")
    op.drop_table("messages")
    op.drop_index("ix_interviews_status", table_name="interviews")
    op.drop_index("ix_interviews_job_id", table_name="interviews")
    op.drop_index("ix_interviews_resume_id", table_name="interviews")
    op.drop_index("ix_interviews_user_id", table_name="interviews")
    op.drop_table("interviews")
