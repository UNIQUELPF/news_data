"""add_user_vip_expire

Revision ID: 008
Revises: 007
Create Date: 2026-05-23 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '008'
down_revision = '007'
branch_labels = None
depends_on = None

def upgrade():
    op.execute("""
    ALTER TABLE users ADD COLUMN IF NOT EXISTS vip_expire_at TIMESTAMP WITH TIME ZONE;
    """)

def downgrade():
    op.execute("""
    ALTER TABLE users DROP COLUMN IF EXISTS vip_expire_at;
    """)
