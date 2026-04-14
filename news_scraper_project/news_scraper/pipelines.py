import hashlib
from urllib.parse import urlparse

import psycopg2
from pipeline.domestic_taxonomy import infer_domestic_location, split_organization_and_company


class PostgresPipeline:
    def __init__(self, crawler=None):
        self.crawler = crawler
        self.connection = None
        self.cursor = None
        self._ensured_tables = set()
        self.enable_unified_pipeline = True
        self.enable_legacy_tables = True
        self.enabled = True

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler=crawler)

    def open_spider(self):
        spider = getattr(self.crawler, "spider", None)
        if spider is None:
            self.enabled = False
            return

        self.enabled = spider.settings.getbool('ENABLE_POSTGRES_PIPELINE', True)
        if not self.enabled:
            spider.logger.info("Postgres pipeline disabled by ENABLE_POSTGRES_PIPELINE=0")
            return

        settings = spider.settings.get('POSTGRES_SETTINGS')
        self.enable_unified_pipeline = spider.settings.getbool('ENABLE_UNIFIED_PIPELINE', True)
        self.enable_legacy_tables = spider.settings.getbool('ENABLE_LEGACY_TABLES', True)
        try:
            self.connection = psycopg2.connect(
                dbname=settings['dbname'],
                user=settings['user'],
                password=settings['password'],
                host=settings['host'],
                port=settings['port']
            )
            self.cursor = self.connection.cursor()
        except psycopg2.OperationalError as exc:
            self.enabled = False
            spider.logger.error(
                "Postgres pipeline unavailable: %s. "
                "Use ENABLE_POSTGRES_PIPELINE=0 for local dry runs or configure POSTGRES_HOST.",
                exc,
            )

    def close_spider(self):
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()

    def process_item(self, item):
        if not self.enabled:
            return item

        spider = getattr(self.crawler, "spider", None)
        if spider is None:
            return item

        table_name = getattr(spider, 'target_table', None)
        if not table_name:
            table_name = self._fallback_table_name(spider.name)
            if not table_name:
                spider.logger.error(f"No target table defined for spider {spider.name}")
                return item

        try:
            normalized = self._normalize_item(item, spider, table_name)
            if not normalized["url"]:
                spider.logger.warning("Skipping item without URL")
                return item

            if self.enable_unified_pipeline:
                self._ensure_unified_tables()
                source_id = self._upsert_source(spider, table_name, normalized)
                self._upsert_article(source_id, normalized)

            if self.enable_legacy_tables:
                self._ensure_legacy_table(table_name)
                self._upsert_legacy_item(table_name, normalized)

            self.connection.commit()
            spider.logger.info(f"Saved to DB: {normalized['url']}")
        except Exception as e:
            spider.logger.error(f"Error saving to DB: {e}")
            self.connection.rollback()
        return item

    def _ensure_legacy_table(self, table_name):
        if table_name in self._ensured_tables:
            return

        self.cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                id SERIAL PRIMARY KEY,
                url TEXT UNIQUE NOT NULL,
                title TEXT,
                content TEXT,
                publish_time TIMESTAMP,
                author TEXT,
                language TEXT,
                section TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self.connection.commit()
        self._ensured_tables.add(table_name)

    def _ensure_unified_tables(self):
        if "__unified_schema__" in self._ensured_tables:
            return

        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS sources (
                id BIGSERIAL PRIMARY KEY,
                spider_name TEXT NOT NULL UNIQUE,
                display_name TEXT,
                domain TEXT,
                country_code TEXT,
                country TEXT,
                organization TEXT,
                legacy_table TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self.cursor.execute("ALTER TABLE sources ADD COLUMN IF NOT EXISTS country_code TEXT")
        
        self.cursor.execute(
            """
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
            )
            """
        )
        self.cursor.execute("ALTER TABLE articles ADD COLUMN IF NOT EXISTS country_code TEXT")
        self.cursor.execute("ALTER TABLE articles ADD COLUMN IF NOT EXISTS company TEXT")
        self.cursor.execute("ALTER TABLE articles ADD COLUMN IF NOT EXISTS province TEXT")
        self.cursor.execute("ALTER TABLE articles ADD COLUMN IF NOT EXISTS city TEXT")
        self.cursor.execute(
            """
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
            )
            """
        )
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS article_chunks (
                id BIGSERIAL PRIMARY KEY,
                article_id BIGINT NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
                chunk_index INTEGER NOT NULL,
                content_text TEXT NOT NULL,
                token_count INTEGER,
                embedding_status TEXT NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(article_id, chunk_index)
            )
            """
        )
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS article_embeddings (
                id BIGSERIAL PRIMARY KEY,
                article_id BIGINT NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
                chunk_id BIGINT REFERENCES article_chunks(id) ON DELETE CASCADE,
                chunk_index INTEGER NOT NULL,
                embedding_model TEXT NOT NULL,
                embedding_dimensions INTEGER,
                embedding_vector JSONB NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(article_id, chunk_index, embedding_model)
            )
            """
        )
        self.connection.commit()
        self._ensured_tables.add("__unified_schema__")

    def _upsert_source(self, spider, table_name, normalized):
        self.cursor.execute(
            """
            INSERT INTO sources (
                spider_name,
                display_name,
                domain,
                country_code,
                country,
                organization,
                legacy_table,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (spider_name) DO UPDATE SET
                display_name = EXCLUDED.display_name,
                domain = EXCLUDED.domain,
                country_code = COALESCE(EXCLUDED.country_code, sources.country_code),
                country = COALESCE(EXCLUDED.country, sources.country),
                organization = COALESCE(EXCLUDED.organization, sources.organization),
                legacy_table = EXCLUDED.legacy_table,
                updated_at = CURRENT_TIMESTAMP
            RETURNING id
            """,
            (
                spider.name,
                self._sanitize_value(getattr(spider, "source_name", None) or spider.name),
                normalized["domain"],
                normalized["country_code"],
                normalized["country"],
                normalized["organization"],
                table_name,
            ),
        )
        return self.cursor.fetchone()[0]

    def _upsert_article(self, source_id, normalized):
        self.cursor.execute(
            """
            INSERT INTO articles (
                source_id,
                source_url,
                title_original,
                content_original,
                publish_time,
                author,
                language,
                section,
                country_code,
                country,
                organization,
                company,
                province,
                city,
                category,
                legacy_table,
                content_hash,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (source_url) DO UPDATE SET
                source_id = EXCLUDED.source_id,
                title_original = EXCLUDED.title_original,
                content_original = EXCLUDED.content_original,
                publish_time = COALESCE(EXCLUDED.publish_time, articles.publish_time),
                author = EXCLUDED.author,
                language = EXCLUDED.language,
                section = EXCLUDED.section,
                country_code = COALESCE(EXCLUDED.country_code, articles.country_code),
                country = COALESCE(EXCLUDED.country, articles.country),
                organization = COALESCE(EXCLUDED.organization, articles.organization),
                company = COALESCE(EXCLUDED.company, articles.company),
                province = COALESCE(EXCLUDED.province, articles.province),
                city = COALESCE(EXCLUDED.city, articles.city),
                category = COALESCE(EXCLUDED.category, articles.category),
                legacy_table = EXCLUDED.legacy_table,
                content_hash = EXCLUDED.content_hash,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                source_id,
                normalized["url"],
                normalized["title"],
                normalized["content"],
                normalized["publish_time"],
                normalized["author"],
                normalized["language"],
                normalized["section"],
                normalized["country_code"],
                normalized["country"],
                normalized["organization"],
                normalized["company"],
                normalized["province"],
                normalized["city"],
                normalized["category"],
                normalized["legacy_table"],
                normalized["content_hash"],
            ),
        )

    def _upsert_legacy_item(self, table_name, normalized):
        if normalized["section"]:
            self.cursor.execute(
                f"""
                INSERT INTO {table_name} (url, title, content, publish_time, author, language, section)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (url) DO UPDATE SET
                    title = EXCLUDED.title,
                    content = EXCLUDED.content,
                    publish_time = COALESCE(EXCLUDED.publish_time, {table_name}.publish_time),
                    author = EXCLUDED.author,
                    language = EXCLUDED.language,
                    section = EXCLUDED.section
                """,
                (
                    normalized["url"],
                    normalized["title"],
                    normalized["content"],
                    normalized["publish_time"],
                    normalized["author"],
                    normalized["language"],
                    normalized["section"],
                ),
            )
            return

        self.cursor.execute(
            f"""
            INSERT INTO {table_name} (url, title, content, publish_time, author, language)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (url) DO UPDATE SET
                title = EXCLUDED.title,
                content = EXCLUDED.content,
                publish_time = COALESCE(EXCLUDED.publish_time, {table_name}.publish_time),
                author = EXCLUDED.author,
                language = EXCLUDED.language
            """,
            (
                normalized["url"],
                normalized["title"],
                normalized["content"],
                normalized["publish_time"],
                normalized["author"],
                normalized["language"],
            ),
        )

    def _normalize_item(self, item, spider, table_name):
        url = self._sanitize_value(item.get('url'))
        title = self._sanitize_value(item.get('title'))
        content = self._sanitize_value(item.get('content'))
        author = self._sanitize_value(item.get('author'))
        import re
        explicit_lang = self._sanitize_value(item.get('language'))
        combined_text = (title or '') + ' ' + (content or '')
        if combined_text:
            zh_chars = len(re.findall(r'[\u4e00-\u9fa5]', combined_text))
            if len(combined_text) > 0 and (zh_chars / len(combined_text)) > 0.05:
                language = 'zh-CN'
            else:
                language = explicit_lang
        else:
            language = explicit_lang
        section = self._sanitize_value(item.get('section') or item.get('channel') or item.get('module'))
        category = self._sanitize_value(item.get('category') or item.get('type'))
        
        explicit_country = item.get('country') or getattr(spider, 'country', None)
        inferred_code, inferred_name = self._infer_country_data(spider.name)
        
        country_code = self._sanitize_value(item.get('country_code') or getattr(spider, 'country_code', None) or inferred_code)
        country = self._sanitize_value(explicit_country or inferred_name)
        
        raw_org = self._sanitize_value(item.get('organization') or getattr(spider, 'organization', None))
        organization, company = split_organization_and_company(raw_org)
        if not company:
            company = self._sanitize_value(item.get('company') or item.get('companies') or item.get('entity'))
        publish_time = item.get('publish_time') or item.get('publish_date')
        domain = self._sanitize_value(self._extract_domain(url, spider))
        content_hash = self._build_content_hash(url, title, content)
        province = None
        city = None
        if country_code == 'CHN':
            province, city = infer_domestic_location(title, content)

        return {
            "url": url,
            "title": title,
            "content": content,
            "author": author,
            "language": language,
            "section": section,
            "category": category,
            "country_code": country_code,
            "country": country,
            "organization": organization,
            "company": company,
            "province": province,
            "city": city,
            "publish_time": publish_time,
            "domain": domain,
            "legacy_table": table_name,
            "content_hash": content_hash,
        }

    def _fallback_table_name(self, spider_name):
        fallback_tables = {
            'danas': 'ser_danas',
            'b92': 'ser_b92',
            'politika': 'ser_politika',
            'economy': 'aze_economy',
            'bfb': 'aze_bfb',
        }
        # Most spiders can safely use their own spider name as the legacy table
        # name; keep explicit mappings only for historical aliases.
        return fallback_tables.get(spider_name, spider_name)

    def _infer_country_data(self, spider_name):
        # Maps spider prefixes to (ISO 3166-1 alpha-3 code, localized name)
        # Using Chinese localization for frontend presentation friendliness.
        country_map = {
            'usa': ('USA', '美国'),
            'jp': ('JPN', '日本'),
            'japan': ('JPN', '日本'),
            'mexico': ('MEX', '墨西哥'),
            'pt': ('PRT', '葡萄牙'),
            'mm': ('MMR', '缅甸'),
            'ba': ('BIH', '波黑'),
            'mn': ('MNG', '蒙古'),
            'bn': ('BRN', '文莱'),
            'argentina': ('ARG', '阿根廷'),
            'albania': ('ALB', '阿尔巴尼亚'),
            'austria': ('AUT', '奥地利'),
            'bahrain': ('BHR', '巴林'),
            'denmark': ('DNK', '丹麦'),
            'france': ('FRA', '法国'),
            'laos': ('LAO', '老挝'),
            'netherlands': ('NLD', '荷兰'),
            'uk': ('GBR', '英国'),
            'india': ('IND', '印度'),
            'egypt': ('EGY', '埃及'),
            'malaysia': ('MYS', '马来西亚'),
            'ser': ('SRB', '塞尔维亚'),
            'aze': ('AZE', '阿塞拜疆'),
            'ee': ('EST', '爱沙尼亚'),
            'finland': ('FIN', '芬兰'),
            'germany': ('DEU', '德国'),
            'greece': ('GRC', '希腊'),
            'italy': ('ITA', '意大利'),
            'spain': ('ESP', '西班牙'),
            'sweden': ('SWE', '瑞典'),
            'switzerland': ('CHE', '瑞士'),
            'turkey': ('TUR', '土耳其'),
            'caixin': ('CHN', '中国'),
            'news': ('CHN', '中国'),
        }
        prefix = spider_name.split('_', 1)[0]
        # Return matched tuple, or fallback to (None, prefix capitalized)
        return country_map.get(prefix, (None, prefix.capitalize() if prefix else None))

    def _extract_domain(self, url, spider):
        if url:
            return urlparse(url).netloc or None

        allowed_domains = getattr(spider, 'allowed_domains', None) or []
        return allowed_domains[0] if allowed_domains else None

    def _build_content_hash(self, url, title, content):
        joined = "||".join(filter(None, [url, title, content]))
        if not joined:
            return None
        return hashlib.sha256(joined.encode("utf-8")).hexdigest()

    def _sanitize_value(self, value):
        if value is None:
            return None
        return str(value).replace("\x00", " ").strip()
