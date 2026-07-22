"""add persisted interview progress and answer validity"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "j6e7f8a9b0c1"
down_revision: Union[str, None] = "i5d6e7f8a9b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "interviews",
        sa.Column("completed_questions", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "interviews",
        sa.Column("current_question_index", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column("messages", sa.Column("is_valid_answer", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("messages", "is_valid_answer")
    op.drop_column("interviews", "current_question_index")
    op.drop_column("interviews", "completed_questions")
