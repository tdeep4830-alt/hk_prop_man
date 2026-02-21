"""Add court_case and guideline to doctype enum.

Revision ID: 002
Revises: 001
Create Date: 2026-02-19

"""
from typing import Sequence, Union

from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ALTER TYPE ADD VALUE cannot run inside a transaction in PostgreSQL.
    op.execute("COMMIT")
    op.execute("ALTER TYPE doctype ADD VALUE IF NOT EXISTS 'court_case'")
    op.execute("ALTER TYPE doctype ADD VALUE IF NOT EXISTS 'guideline'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values directly.
    # A full enum rebuild would be needed; skipped for safety.
    pass
