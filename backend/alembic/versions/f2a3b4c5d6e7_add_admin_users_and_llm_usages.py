"""add administrator accounts and LLM usage records

Revision ID: f2a3b4c5d6e7
Revises: e8f1a2b3c4d5
Create Date: 2026-07-21

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f2a3b4c5d6e7"
down_revision: Union[str, Sequence[str], None] = "e8f1a2b3c4d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "admin_users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )
    op.create_index("ix_admin_users_username", "admin_users", ["username"], unique=True)

    op.create_table(
        "llm_usages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("feature", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=80), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("completion_tokens", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("total_tokens", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("latency_ms", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_llm_usages_user_id", "llm_usages", ["user_id"], unique=False)
    op.create_index("ix_llm_usages_feature", "llm_usages", ["feature"], unique=False)
    op.create_index("ix_llm_usages_created_at", "llm_usages", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_llm_usages_created_at", table_name="llm_usages")
    op.drop_index("ix_llm_usages_feature", table_name="llm_usages")
    op.drop_index("ix_llm_usages_user_id", table_name="llm_usages")
    op.drop_table("llm_usages")
    op.drop_index("ix_admin_users_username", table_name="admin_users")
    op.drop_table("admin_users")
