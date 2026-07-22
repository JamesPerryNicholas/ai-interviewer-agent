"""add career status to users"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "i5d6e7f8a9b0"
down_revision: Union[str, None] = "h4c5d6e7f8a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "career_status",
            sa.String(length=20),
            server_default="实习求职",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "career_status")
