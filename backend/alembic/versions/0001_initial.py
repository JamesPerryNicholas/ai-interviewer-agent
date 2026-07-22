"""Initial empty migration for the project foundation."""

from typing import Sequence, Union


revision: str = "0001_initial"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create no tables in phase one; models are intentionally deferred."""


def downgrade() -> None:
    """Reverse the phase-one no-op migration."""

