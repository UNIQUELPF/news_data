"""refactor users for password

Revision ID: 006
Revises: 005
Create Date: 2026-05-12 09:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Drop verification_codes table
    op.drop_table('verification_codes')

    # 2. Add columns to users table
    op.add_column('users', sa.Column('username', sa.String(length=100), nullable=True))
    op.add_column('users', sa.Column('password_hash', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('phone', sa.String(length=20), nullable=True))
    
    # 3. Make email nullable (it was not nullable in migration 004)
    op.alter_column('users', 'email',
               existing_type=sa.VARCHAR(length=255),
               nullable=True)

    # 4. Set existing email as username for any existing users
    op.execute("UPDATE users SET username = email WHERE username IS NULL")
    
    # 5. Make username unique and not nullable
    op.create_unique_constraint('uq_users_username', 'users', ['username'])
    op.alter_column('users', 'username', nullable=False)

    # 6. Insert default admin account
    # Password: admin123 -> news_salt:0266d8018c59640e0ea48b868aada34befc0bb111bfa8ddeb18f38aca4ac900e
    op.execute("""
        INSERT INTO users (email, username, password_hash, nickname, role, is_active)
        VALUES ('admin@example.com', 'admin', 'news_salt:0266d8018c59640e0ea48b868aada34befc0bb111bfa8ddeb18f38aca4ac900e', '管理员', 'admin', true)
        ON CONFLICT (username) DO NOTHING
    """)


def downgrade():
    op.create_table('verification_codes',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('code', sa.String(length=6), nullable=False),
        sa.Column('purpose', sa.String(length=20), server_default='login', nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('used', sa.Boolean(), server_default='false', nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=True),
    )
    op.drop_constraint('uq_users_username', 'users', type_='unique')
    op.drop_column('users', 'phone')
    op.drop_column('users', 'password_hash')
    op.drop_column('users', 'username')
    op.alter_column('users', 'email',
               existing_type=sa.VARCHAR(length=255),
               nullable=False)
