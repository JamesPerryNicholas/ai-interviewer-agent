"""snapshot interview questions and persist avatar bytes"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "l8m9n0o1p2q3"
down_revision: Union[str, None] = "k7f8a9b0c1d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("avatar_data", sa.LargeBinary(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("avatar_content_type", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "interviews",
        sa.Column("total_questions", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "interviews",
        sa.Column(
            "question_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )

    # Existing completed sessions must keep the number they actually completed.
    # New sessions will store an exact question snapshot when they start.
    op.execute(
        sa.text(
            """
            UPDATE interviews
            SET total_questions = CASE
                WHEN status = 'completed' AND completed_questions > 0
                    THEN completed_questions
                ELSE COALESCE((
                    SELECT COUNT(*)::integer
                    FROM questions
                    WHERE questions.job_id = interviews.job_id
                ), 0)
            END
            WHERE total_questions = 0
            """
        )
    )


def downgrade() -> None:
    op.drop_column("interviews", "question_snapshot")
    op.drop_column("interviews", "total_questions")
    op.drop_column("users", "avatar_content_type")
    op.drop_column("users", "avatar_data")
