"""add successful login records"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "h4c5d6e7f8a9"
down_revision: Union[str, None] = "g3b4c5d6e7f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "login_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("login_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_login_records_user_id", "login_records", ["user_id"], unique=False)
    op.create_index("ix_login_records_login_at", "login_records", ["login_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_login_records_login_at", table_name="login_records")
    op.drop_index("ix_login_records_user_id", table_name="login_records")
    op.drop_table("login_records")
