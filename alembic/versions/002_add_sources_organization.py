"""add organization to sources

Revision ID: 002_add_sources_organization
Revises: 001_init_v2_schema
Create Date: 2026-04-27 09:58:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "002_add_sources_organization"
down_revision: Union[str, None] = "001_init_v2_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE sources ADD COLUMN IF NOT EXISTS organization TEXT;")


def downgrade() -> None:
    op.execute("ALTER TABLE sources DROP COLUMN IF EXISTS organization;")
