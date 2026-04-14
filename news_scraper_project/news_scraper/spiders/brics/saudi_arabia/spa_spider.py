# 沙特阿拉伯spa spider爬虫，负责抓取对应站点、机构或栏目内容。

import json
from datetime import datetime, timedelta, timezone

import psycopg2
import scrapy
from bs4 import BeautifulSoup
from news_scraper.items import NewsItem
from news_scraper.settings import POSTGRES_SETTINGS
from news_scraper.utils import get_incremental_state


class SaudiPressAgencySpider(scrapy.Spider):
    """
    Saudi Press Agency (SPA) spider using Native JSON API for pagination.
    Supports full scan (from 2026-01-01) and incremental modes.
    """
    name = "saudi_spa"

    country_code = 'SAU'

    country = '沙特阿拉伯'
    allowed_domains = ["portalapi.spa.gov.sa"]

    target_table = "saudi_spa_news"
    default_cutoff = datetime(2026, 1, 1)

    custom_settings = {
        "DOWNLOAD_DELAY": 0.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 5,
        "RANDOMIZE_DOWNLOAD_DELAY": True,
    }

    def __init__(self, full_scan="false", start_date=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.full_scan = str(full_scan).lower() in ("1", "true", "yes")
        self.cutoff_date = self._init_db_and_get_cutoff()
        self.target_timezone = timezone(timedelta(hours=8))
        if start_date:
            try:
                self.cutoff_date = datetime.strptime(str(start_date), "%Y-%m-%d")
                self.logger.info(f"Using custom start_date cutoff: {self.cutoff_date}")
            except ValueError:
                self.logger.warning(f"Invalid start_date '{start_date}', expected YYYY-MM-DD. Using cutoff {self.cutoff_date}")
        self.seen_urls = set()

    def _init_db_and_get_cutoff(self):
        try:
            conn = psycopg2.connect(**POSTGRES_SETTINGS)
            cur = conn.cursor()
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self.target_table} (
                    id SERIAL PRIMARY KEY,
                    url VARCHAR(500) UNIQUE,
                    title VARCHAR(500),
                    content TEXT,
                    publish_time TIMESTAMP,
                    author VARCHAR(255),
                    language VARCHAR(50),
                    section VARCHAR(100),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()

            cur.close()
            conn.close()

            if self.full_scan:
                return self.default_cutoff

            state = get_incremental_state(
                self.settings,
                spider_name=self.name,
                table_name=self.target_table,
                default_cutoff=self.default_cutoff,
                full_scan=False,
            )
            return max(state["cutoff_date"], self.default_cutoff)
        except Exception as exc:
            self.logger.error(f"DB init failed: {exc}")
            return self.default_cutoff

    def start_requests(self):
        params_ar = "by_latest=1&per_page=50&w_content=1&w_tag=1&page=1&l=ar"
        url = f"https://portalapi.spa.gov.sa/api/v1/news?{params_ar}"
        yield scrapy.Request(
            url=url,
            callback=self.parse_api_page,
            meta={'page': 1, 'lang': 'ar', 'failed_count': 0},
            dont_filter=True
        )

    def parse_api_page(self, response):
        try:
            data = json.loads(response.text)
        except Exception as e:
            self.logger.error(f"Failed to parse API JSON on {response.url}: {e}")
            failed_count = response.meta.get('failed_count', 0) + 1
            if failed_count < 3:
                yield response.request.replace(meta={'page': response.meta['page'], 'lang': response.meta['lang'], 'failed_count': failed_count}, dont_filter=True)
            return

        items = data.get('data', [])
        self.logger.info(f"Fetched page {response.meta['page']} - items count: {len(items)}")

        if not items:
            self.logger.info(f"No items found on page {response.meta['page']}, stopping.")
            return

        reached_cutoff = False

        for item in items:
            news_id = item.get('uuid')
            title = item.get('title', '').strip()
            
            if not news_id or not title:
                continue

            article_url = f"https://www.spa.gov.sa/N{news_id.replace('N','')}"

            # Parse publish time
            pub_time = None
            published_at = item.get('published_at')
            if published_at:
                try:
                    pub_time = datetime.fromtimestamp(
                        published_at, tz=timezone.utc
                    ).astimezone(self.target_timezone).replace(tzinfo=None)
                except Exception:
                    pass
            
            if not pub_time:
                pub_time = datetime.now()

            # Check cutoff
            if pub_time < self.cutoff_date:
                self.logger.debug(f"Reached cutoff {self.cutoff_date} with article from {pub_time} - Stopping pagination")
                reached_cutoff = True
                continue

            # Extract Content
            content_html = item.get('content', '')
            if content_html:
                soup = BeautifulSoup(content_html, 'html.parser')
                content = soup.get_text(separator='\n', strip=True)
            else:
                content = f"[أخبار] {title}"

            # Section & Language
            category = item.get('category', {})
            section = category.get('name', 'عام') if isinstance(category, dict) else 'عام'
            language = item.get('locale', response.meta['lang'])
            author = "وكالة الأنباء السعودية"

            news_item = NewsItem(
                url=article_url,
                title=title,
                content=content,
                publish_time=pub_time,
                author=author,
                language=language,
                section=section
            )
            yield news_item

        # Continue pagination if we haven't reached the cutoff
        if not reached_cutoff:
            current_page = response.meta['page']
            meta_pagination = data.get('meta', {})
            last_page = meta_pagination.get('last_page', 999999)
            
            if current_page < last_page:
                next_page = current_page + 1
                params = f"by_latest=1&per_page=50&w_content=1&w_tag=1&page={next_page}&l={response.meta['lang']}"
                next_url = f"https://portalapi.spa.gov.sa/api/v1/news?{params}"
                
                yield scrapy.Request(
                    url=next_url,
                    callback=self.parse_api_page,
                    meta={'page': next_page, 'lang': response.meta['lang'], 'failed_count': 0},
                    dont_filter=True
                )
            else:
                self.logger.info("Reached last page according to API meta.")
