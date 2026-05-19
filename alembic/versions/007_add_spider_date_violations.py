"""add_spider_date_violations

Revision ID: 007
Revises: 006
Create Date: 2026-05-19 16:21:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None

def upgrade():
    op.execute("""
    CREATE TABLE IF NOT EXISTS spider_date_violations (
        id            BIGSERIAL PRIMARY KEY,
        spider_name   TEXT NOT NULL,
        violation_type TEXT NOT NULL,
        article_url   TEXT,
        article_title TEXT,
        raw_date      TEXT,
        detected_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        resolved      BOOLEAN DEFAULT FALSE
    );
    CREATE INDEX IF NOT EXISTS idx_violations_spider ON spider_date_violations(spider_name);
    CREATE INDEX IF NOT EXISTS idx_violations_unresolved ON spider_date_violations(resolved) WHERE resolved = FALSE;
    """)

def downgrade():
    op.execute("DROP TABLE IF EXISTS spider_date_violations;")
