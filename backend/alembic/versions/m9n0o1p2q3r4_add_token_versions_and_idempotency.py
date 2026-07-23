"""Add token revocation versions and request idempotency keys.

Revision ID: m9n0o1p2q3r4
Revises: l8m9n0o1p2q3
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m9n0o1p2q3r4"
down_revision: Union[str, None] = "l8m9n0o1p2q3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("token_version", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "admin_users",
        sa.Column("token_version", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "interviews",
        sa.Column("start_request_id", sa.String(length=64), nullable=True),
    )
    op.create_unique_constraint(
        "uq_interviews_user_start_request",
        "interviews",
        ["user_id", "start_request_id"],
    )
    op.add_column(
        "messages",
        sa.Column("client_request_id", sa.String(length=64), nullable=True),
    )
    op.create_unique_constraint(
        "uq_messages_interview_client_request",
        "messages",
        ["interview_id", "client_request_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_messages_interview_client_request", "messages", type_="unique"
    )
    op.drop_column("messages", "client_request_id")
    op.drop_constraint(
        "uq_interviews_user_start_request", "interviews", type_="unique"
    )
    op.drop_column("interviews", "start_request_id")
    op.drop_column("admin_users", "token_version")
    op.drop_column("users", "token_version")
