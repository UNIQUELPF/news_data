import hashlib
import json
from urllib.parse import urlparse
import psycopg2
from pipeline.domestic_taxonomy import infer_domestic_location, split_organization_and_company

class PostgresPipeline:
    def __init__(self, crawler=None):
        self.crawler = crawler
        self.connection = None
        self.cursor = None
        self.enabled = True

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler=crawler)

    def open_spider(self, spider=None):
        if spider is None:
            spider = getattr(self.crawler, "spider", None)
        if spider is None:
            self.enabled = False
            return

        self.enabled = spider.settings.getbool('ENABLE_POSTGRES_PIPELINE', True)
        if not self.enabled:
            spider.logger.info("Postgres pipeline disabled by ENABLE_POSTGRES_PIPELINE=0")
            return

        settings = spider.settings.get('POSTGRES_SETTINGS')
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
            spider.logger.error(f"Postgres pipeline unavailable: {exc}")

    def close_spider(self):
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()

    def process_item(self, item, spider=None):
        if not self.enabled:
            return item

        if spider is None:
            spider = getattr(self.crawler, "spider", None)
        
        if spider is None:
            # Last resort log using print or just ignore if we can't find a logger
            return item

        try:
            normalized = self._normalize_item(item, spider)
            if not normalized["url"]:
                spider.logger.warning("Skipping item without URL")
                return item

            # 1. Ensure the source exists
            source_id = self._upsert_source(spider, normalized)
            
            # 2. Insert/Update the article in the new unified table
            self._upsert_article(source_id, normalized)

            self.connection.commit()
            spider.logger.info(f"Saved to V2 DB: {normalized['url']}")
        except Exception as e:
            spider.logger.error(f"Error saving to V2 DB: {e}")
            self.connection.rollback()
        return item

    def _upsert_source(self, spider, normalized):
        self.cursor.execute(
            """
            INSERT INTO sources (
                spider_name,
                display_name,
                domain,
                country_code,
                country,
                organization,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (spider_name) DO UPDATE SET
                display_name = EXCLUDED.display_name,
                domain = EXCLUDED.domain,
                country_code = COALESCE(EXCLUDED.country_code, sources.country_code),
                country = COALESCE(EXCLUDED.country, sources.country),
                organization = COALESCE(EXCLUDED.organization, sources.organization),
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
                content_raw_html,
                content_cleaned,
                content_markdown,
                content_plain,
                images,
                publish_time,
                author,
                language,
                section,
                country_code,
                country,
                company,
                province,
                city,
                category,
                content_hash,
                extraction_status,
                updated_at
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'completed', CURRENT_TIMESTAMP
            )
            ON CONFLICT (source_url) DO UPDATE SET
                source_id = EXCLUDED.source_id,
                title_original = EXCLUDED.title_original,
                content_raw_html = EXCLUDED.content_raw_html,
                content_cleaned = EXCLUDED.content_cleaned,
                content_markdown = EXCLUDED.content_markdown,
                content_plain = EXCLUDED.content_plain,
                images = EXCLUDED.images,
                publish_time = COALESCE(EXCLUDED.publish_time, articles.publish_time),
                author = EXCLUDED.author,
                language = EXCLUDED.language,
                section = EXCLUDED.section,
                country_code = COALESCE(EXCLUDED.country_code, articles.country_code),
                country = COALESCE(EXCLUDED.country, articles.country),
                company = COALESCE(EXCLUDED.company, articles.company),
                province = COALESCE(EXCLUDED.province, articles.province),
                city = COALESCE(EXCLUDED.city, articles.city),
                category = COALESCE(EXCLUDED.category, articles.category),
                content_hash = EXCLUDED.content_hash,
                extraction_status = 'completed',
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                source_id,
                normalized["url"],
                normalized["title"],
                normalized["raw_html"],
                normalized["content_cleaned"],
                normalized["content_markdown"],
                normalized["content_plain"],
                json.dumps(normalized["images"]),
                normalized["publish_time"],
                normalized["author"],
                normalized["language"],
                normalized["section"],
                normalized["country_code"],
                normalized["country"],
                normalized["company"],
                normalized["province"],
                normalized["city"],
                normalized["category"],
                normalized["content_hash"],
            ),
        )

    def _normalize_item(self, item, spider=None):
        if spider is None:
            spider = getattr(self.crawler, "spider", None)
        
        spider_name = spider.name if spider else "unknown"
        
        url = self._sanitize_value(item.get('url'))
        title = self._sanitize_value(item.get('title'))
        
        # New fields from ContentEngine
        raw_html = item.get('raw_html')
        content_cleaned = item.get('content_cleaned')
        content_markdown = item.get('content_markdown')
        content_plain = item.get('content_plain') or item.get('content') # Fallback to legacy
        images = item.get('images') or []
        
        author = self._sanitize_value(item.get('author'))
        
        import re
        explicit_lang = self._sanitize_value(item.get('language'))
        combined_text = (title or '') + ' ' + (content_plain or '')
        if combined_text:
            zh_chars = len(re.findall(r'[\u4e00-\u9fa5]', combined_text))
            if len(combined_text) > 0 and (zh_chars / len(combined_text)) > 0.05:
                language = 'zh-CN'
            else:
                language = explicit_lang
        else:
            language = explicit_lang
            
        section = self._sanitize_value(item.get('section') or item.get('channel'))
        category = self._sanitize_value(item.get('category'))
        
        # Metadata logic
        explicit_country = item.get('country') or (getattr(spider, 'country', None) if spider else None)
        inferred_code, inferred_name = self._infer_country_data(spider_name)
        country_code = self._sanitize_value(item.get('country_code') or (getattr(spider, 'country_code', None) if spider else None) or inferred_code)
        country = self._sanitize_value(explicit_country or inferred_name)
        raw_org = self._sanitize_value(item.get('organization') or (getattr(spider, 'organization', None) if spider else None))
        organization, company = split_organization_and_company(raw_org)
        
        publish_time = item.get('publish_time')
        domain = self._sanitize_value(urlparse(url).netloc if url else None)
        content_hash = self._build_content_hash(url, title, content_plain)
        
        province = None
        city = None
        if country_code == 'CHN':
            province, city = infer_domestic_location(title, content_plain)

        return {
            "url": url,
            "title": title,
            "raw_html": raw_html,
            "content_cleaned": content_cleaned,
            "content_markdown": content_markdown,
            "content_plain": content_plain,
            "images": images,
            "author": author,
            "language": language,
            "section": section,
            "category": category,
            "country_code": country_code,
            "country": country,
            "organization": organization,
            "company": item.get('company') or company,
            "province": province,
            "city": city,
            "publish_time": publish_time,
            "domain": domain,
            "content_hash": content_hash,
        }

    def _infer_country_data(self, spider_name):
        country_map = {
            'usa': ('USA', '美国'),
            'jp': ('JPN', '日本'),
            'bahrain': ('BHR', '巴林'),
            'uae': ('ARE', '阿联酋'),
            'saudi': ('SAU', '沙特'),
            'caixin': ('CHN', '中国'),
        }
        prefix = spider_name.split('_', 1)[0]
        return country_map.get(prefix, (None, prefix.capitalize() if prefix else None))

    def _build_content_hash(self, url, title, content):
        joined = "||".join(filter(None, [url, title, content]))
        return hashlib.sha256(joined.encode("utf-8")).hexdigest() if joined else None

    def _sanitize_value(self, value):
        if value is None:
            return None
        return str(value).replace("\x00", " ").strip()
