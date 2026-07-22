"""add original filename to resumes

Revision ID: d4e6f8a1b2c3
Revises: c7b2d4e91f10
Create Date: 2026-07-20

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4e6f8a1b2c3"
down_revision: Union[str, Sequence[str], None] = "c7b2d4e91f10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Store the original client-visible filename separately from the safe path."""

    op.add_column(
        "resumes",
        sa.Column("original_filename", sa.String(length=255), nullable=True),
    )
    op.execute(
        """
        UPDATE resumes
        SET original_filename = regexp_replace(file_url, '^.*/', '')
        WHERE original_filename IS NULL
        """
    )
    op.alter_column("resumes", "original_filename", nullable=False)


def downgrade() -> None:
    """Remove the original filename column."""

    op.drop_column("resumes", "original_filename")
