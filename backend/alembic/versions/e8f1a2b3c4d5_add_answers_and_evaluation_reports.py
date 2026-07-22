"""add interview answers and evaluation reports

Revision ID: e8f1a2b3c4d5
Revises: d4e6f8a1b2c3
Create Date: 2026-07-20

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "e8f1a2b3c4d5"
down_revision: Union[str, Sequence[str], None] = "d4e6f8a1b2c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create answer audit rows and one report per interview."""

    op.create_table(
        "answers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("interview_id", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=True),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("analysis", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["interview_id"], ["interviews.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_answers_interview_id", "answers", ["interview_id"], unique=False)
    op.create_index("ix_answers_question_id", "answers", ["question_id"], unique=False)

    op.create_table(
        "evaluation_reports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("interview_id", sa.Integer(), nullable=False),
        sa.Column("total_score", sa.Integer(), nullable=False),
        sa.Column("technical_score", sa.Integer(), nullable=False),
        sa.Column("communication_score", sa.Integer(), nullable=False),
        sa.Column("strengths", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("weaknesses", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("suggestions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["interview_id"], ["interviews.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("interview_id"),
    )
    op.create_index("ix_evaluation_reports_interview_id", "evaluation_reports", ["interview_id"], unique=True)


def downgrade() -> None:
    """Remove reports and answer audit rows."""

    op.drop_index("ix_evaluation_reports_interview_id", table_name="evaluation_reports")
    op.drop_table("evaluation_reports")
    op.drop_index("ix_answers_question_id", table_name="answers")
    op.drop_index("ix_answers_interview_id", table_name="answers")
    op.drop_table("answers")
