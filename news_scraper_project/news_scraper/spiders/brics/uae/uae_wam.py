import json
from datetime import datetime

import psycopg2
import scrapy
from bs4 import BeautifulSoup

from news_scraper.items import NewsItem
from news_scraper.settings import POSTGRES_SETTINGS


class UaeWamSpider(scrapy.Spider):
    name = "uae_wam"
    allowed_domains = ["wam.ae"]

    target_table = "uae_wam"
    list_url = "https://www.wam.ae/api/app/views/GetViewByUrl"
    section_url = "https://www.wam.ae/api/app/views/GetSectionArticlesFDto"
    detail_url = "https://www.wam.ae/api/app/articles/GetArticleBySlug"

    default_cutoff = datetime(2026, 1, 1)

    custom_settings = {
        "DOWNLOAD_DELAY": 0.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 8,
    }

    def __init__(self, full_scan="false", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.full_scan = str(full_scan).lower() in ("1", "true", "yes")
        self.cutoff_date = self._init_db_and_get_cutoff()
        self.reached_cutoff = False
        self.seen_slugs = set()

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

            cur.execute(f"SELECT MAX(publish_time) FROM {self.target_table}")
            max_time = cur.fetchone()[0]
            cur.close()
            conn.close()

            if self.full_scan or not max_time:
                return self.default_cutoff
            return max_time
        except Exception as exc:
            self.logger.error(f"DB init failed: {exc}")
            return self.default_cutoff

    def start_requests(self):
        yield scrapy.Request(
            url=f"{self.list_url}?url=ar/list/latest-news",
            callback=self.parse_first_page,
            headers={"Accept": "application/json"},
        )

    def parse_first_page(self, response):
        data = json.loads(response.text)
        section = data["sections"][0]["articlesResult"]
        section_info = section["paging"]["sectionInfo"]

        yield from self._parse_articles_list(
            items=section.get("items", []),
            section_info=section_info,
            current_page=section["paging"].get("pageNumber", 0),
            has_next=section["paging"].get("hasNext", False),
        )

    def parse_section_page(self, response):
        data = json.loads(response.text)
        paging = data.get("paging", {})
        items = data.get("items", [])
        section_info = paging.get("sectionInfo")

        yield from self._parse_articles_list(
            items=items,
            section_info=section_info,
            current_page=paging.get("pageNumber", 0),
            has_next=paging.get("hasNext", False),
        )

    def _parse_articles_list(self, items, section_info, current_page, has_next):
        if not items:
            return

        for article in items:
            publish_time = self._parse_datetime(article.get("articleDate"))
            if publish_time and publish_time < self.cutoff_date:
                self.reached_cutoff = True
                continue

            slug_param = article.get("shortCode") or article.get("urlSlug") or article.get("slug")
            if not slug_param or slug_param in self.seen_slugs:
                continue
            self.seen_slugs.add(slug_param)

            yield scrapy.Request(
                url=f"{self.detail_url}?slug={slug_param}",
                callback=self.parse_detail,
                headers={"Accept": "application/json"},
                meta={
                    "list_article": article,
                },
            )

        if has_next and not self.reached_cutoff:
            payload = {
                "sectionInfo": section_info,
                "pageNumber": current_page + 1,
                "pageSize": 20,
            }
            yield scrapy.Request(
                url=self.section_url,
                method="POST",
                body=json.dumps(payload),
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                callback=self.parse_section_page,
            )

    def parse_detail(self, response):
        if response.status == 204:
            return

        detail = json.loads(response.text)

        publish_time = self._parse_datetime(detail.get("articleDate"))
        if publish_time and publish_time < self.cutoff_date:
            return

        title = (detail.get("title") or "").strip()
        if not title:
            return

        body_html = detail.get("body") or ""
        content = self._html_to_text(body_html)
        if not content:
            content = (detail.get("summary") or "").strip()
        if not content:
            return

        short_code = detail.get("shortCode") or response.meta.get("list_article", {}).get("shortCode")
        slug = detail.get("slug") or response.meta.get("list_article", {}).get("slug")
        if short_code and slug:
            article_url = f"https://www.wam.ae/ar/article/{short_code}-{slug}"
        elif short_code:
            article_url = f"https://www.wam.ae/ar/article/{short_code}"
        else:
            article_url = response.url

        categories = detail.get("categories") or []
        section = "WAM"
        if categories and isinstance(categories[0], dict):
            section = categories[0].get("title") or section

        authors = detail.get("articleAuthors") or []
        author = "WAM"
        if authors:
            author = ", ".join([a for a in authors if a])

        item = NewsItem()
        item["url"] = article_url
        item["title"] = title
        item["content"] = content
        item["publish_time"] = publish_time or datetime.now()
        item["author"] = author
        item["language"] = "ar"
        item["section"] = section
        item["scrape_time"] = datetime.now()
        yield item

    def _parse_datetime(self, value):
        if not value:
            return None
        try:
            dt = datetime.fromisoformat(value)
            if dt.tzinfo is not None:
                dt = dt.replace(tzinfo=None)
            return dt
        except Exception:
            return None

    def _html_to_text(self, html):
        if not html:
            return ""
        soup = BeautifulSoup(html, "html.parser")
        paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
        paragraphs = [p for p in paragraphs if p]
        if paragraphs:
            return "\n".join(paragraphs)
        return soup.get_text(" ", strip=True)
