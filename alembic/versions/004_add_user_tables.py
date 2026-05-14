"""add user tables

Revision ID: 004
Revises: 003
Create Date: 2026-05-11 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '004'
down_revision = '003_add_missing_tables'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('users',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('email', sa.String(length=255), nullable=False, unique=True),
        sa.Column('nickname', sa.String(length=100), nullable=True),
        sa.Column('role', sa.String(length=20), server_default='user', nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=True),
        sa.Column('last_login_at', sa.DateTime(), nullable=True),
    )

    op.create_table('verification_codes',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('code', sa.String(length=6), nullable=False),
        sa.Column('purpose', sa.String(length=20), server_default='login', nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('used', sa.Boolean(), server_default='false', nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=True),
    )


def downgrade():
    op.drop_table('verification_codes')
    op.drop_table('users')
