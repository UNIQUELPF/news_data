"""init v2 unified schema

Revision ID: 001_init_v2_schema
Revises: 
Create Date: 2026-04-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001_init_v2_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # sources table
    op.execute("""
    CREATE TABLE IF NOT EXISTS sources (
        id          BIGSERIAL PRIMARY KEY,
        spider_name TEXT NOT NULL UNIQUE,
        display_name TEXT,
        domain      TEXT,
        country_code TEXT,
        country     TEXT,
        language    TEXT,
        created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # articles table
    op.execute("""
    CREATE TABLE IF NOT EXISTS articles (
        id               BIGSERIAL PRIMARY KEY,
        source_id        BIGINT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
        source_url       TEXT NOT NULL UNIQUE,

        title_original   TEXT,
        content_raw_html TEXT,
        content_cleaned  TEXT,
        content_markdown TEXT,
        content_plain    TEXT,

        images           JSONB,
        
        publish_time     TIMESTAMP,
        author           TEXT,
        language         TEXT,
        section          TEXT,
        country_code     TEXT,
        country          TEXT,
        company          TEXT,
        province         TEXT,
        city             TEXT,
        category         TEXT,
        content_hash     TEXT,

        extraction_status  TEXT NOT NULL DEFAULT 'pending',
        translation_status TEXT NOT NULL DEFAULT 'pending',
        embedding_status   TEXT NOT NULL DEFAULT 'pending',

        created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Indexes
    op.execute("CREATE INDEX IF NOT EXISTS idx_articles_source_id ON articles(source_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_articles_publish_time ON articles(publish_time DESC);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_articles_country_code ON articles(country_code);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_articles_category ON articles(category);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_articles_company ON articles(company);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_articles_extraction_status ON articles(extraction_status);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_articles_translation_status ON articles(translation_status);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_articles_embedding_status ON articles(embedding_status);")
    
    # pg_trgm for full text search, needs extension
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
    op.execute("CREATE INDEX IF NOT EXISTS idx_articles_content_plain_trgm ON articles USING gin (content_plain gin_trgm_ops);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_articles_title_trgm ON articles USING gin (title_original gin_trgm_ops);")

    # article_translations table
    op.execute("""
    CREATE TABLE IF NOT EXISTS article_translations (
        id                 BIGSERIAL PRIMARY KEY,
        article_id         BIGINT NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
        target_language    TEXT NOT NULL,
        title_translated   TEXT,
        summary_translated TEXT,
        content_translated TEXT,
        translator         TEXT,
        status             TEXT NOT NULL DEFAULT 'pending',
        created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(article_id, target_language)
    );
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS article_translations CASCADE;")
    op.execute("DROP TABLE IF EXISTS articles CASCADE;")
    op.execute("DROP TABLE IF EXISTS sources CASCADE;")
