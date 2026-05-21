ALTER TABLE sources
    ADD COLUMN IF NOT EXISTS country_code TEXT,
    ADD COLUMN IF NOT EXISTS language TEXT;

ALTER TABLE articles
    ADD COLUMN IF NOT EXISTS content_raw_html TEXT,
    ADD COLUMN IF NOT EXISTS content_cleaned TEXT,
    ADD COLUMN IF NOT EXISTS content_markdown TEXT,
    ADD COLUMN IF NOT EXISTS content_plain TEXT,
    ADD COLUMN IF NOT EXISTS images JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS extraction_status TEXT NOT NULL DEFAULT 'pending';

UPDATE articles
SET content_plain = COALESCE(content_plain, content_original)
WHERE content_plain IS NULL
  AND content_original IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_sources_country_code ON sources(country_code);
CREATE INDEX IF NOT EXISTS idx_articles_extraction_status ON articles(extraction_status);
