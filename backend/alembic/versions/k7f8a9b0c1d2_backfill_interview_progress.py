"""backfill progress for interviews created before answer validation"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "k7f8a9b0c1d2"
down_revision: Union[str, None] = "j6e7f8a9b0c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            WITH question_counts AS (
                SELECT job_id, COUNT(*)::integer AS total_questions
                FROM questions
                GROUP BY job_id
            ), answer_counts AS (
                SELECT
                    i.id AS interview_id,
                    LEAST(
                        COUNT(m.id)::integer,
                        COALESCE(qc.total_questions, 0)
                    ) AS completed_questions
                FROM interviews i
                LEFT JOIN messages m
                    ON m.interview_id = i.id
                    AND m.role = 'user'
                    AND m.is_valid_answer IS NOT FALSE
                LEFT JOIN question_counts qc ON qc.job_id = i.job_id
                WHERE i.completed_questions = 0
                GROUP BY i.id, qc.total_questions
                HAVING COUNT(m.id) > 0
            )
            UPDATE interviews i
            SET
                completed_questions = answer_counts.completed_questions,
                current_question_index = answer_counts.completed_questions
            FROM answer_counts
            WHERE i.id = answer_counts.interview_id
            """
        )
    )


def downgrade() -> None:
    # The backfill is intentionally not reversed; removing it would discard
    # progress that may have been updated after this migration.
    pass
