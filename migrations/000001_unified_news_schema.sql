CREATE TABLE IF NOT EXISTS sources (
    id BIGSERIAL PRIMARY KEY,
    spider_name TEXT NOT NULL UNIQUE,
    display_name TEXT,
    domain TEXT,
    country TEXT,
    organization TEXT,
    legacy_table TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS articles (
    id BIGSERIAL PRIMARY KEY,
    source_id BIGINT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    source_url TEXT NOT NULL UNIQUE,
    title_original TEXT,
    content_original TEXT,
    publish_time TIMESTAMP,
    author TEXT,
    language TEXT,
    section TEXT,
    country_code TEXT,
    country TEXT,
    organization TEXT,
    company TEXT,
    province TEXT,
    city TEXT,
    category TEXT,
    legacy_table TEXT,
    content_hash TEXT,
    translation_status TEXT NOT NULL DEFAULT 'pending',
    embedding_status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_articles_source_id ON articles(source_id);
CREATE INDEX IF NOT EXISTS idx_articles_publish_time ON articles(publish_time DESC);
CREATE INDEX IF NOT EXISTS idx_articles_country ON articles(country);
CREATE INDEX IF NOT EXISTS idx_articles_country_code ON articles(country_code);
CREATE INDEX IF NOT EXISTS idx_articles_organization ON articles(organization);
CREATE INDEX IF NOT EXISTS idx_articles_company ON articles(company);
CREATE INDEX IF NOT EXISTS idx_articles_province ON articles(province);
CREATE INDEX IF NOT EXISTS idx_articles_city ON articles(city);
CREATE INDEX IF NOT EXISTS idx_articles_category ON articles(category);
CREATE INDEX IF NOT EXISTS idx_articles_translation_status ON articles(translation_status);
CREATE INDEX IF NOT EXISTS idx_articles_embedding_status ON articles(embedding_status);

CREATE TABLE IF NOT EXISTS article_translations (
    id BIGSERIAL PRIMARY KEY,
    article_id BIGINT NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    target_language TEXT NOT NULL,
    title_translated TEXT,
    summary_translated TEXT,
    content_translated TEXT,
    translator TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(article_id, target_language)
);


CREATE TABLE IF NOT EXISTS crawl_jobs (
    id BIGSERIAL PRIMARY KEY,
    spider_name TEXT NOT NULL,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP,
    status TEXT NOT NULL DEFAULT 'running',
    items_scraped INTEGER NOT NULL DEFAULT 0,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS crawl_errors (
    id BIGSERIAL PRIMARY KEY,
    spider_name TEXT NOT NULL,
    source_url TEXT,
    error_stage TEXT,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
