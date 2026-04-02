# 印度尼西亚ina news爬虫，负责抓取对应站点、机构或栏目内容。

import re
from datetime import datetime
from urllib.parse import urlparse

import psycopg2
import scrapy
from bs4 import BeautifulSoup

from news_scraper.items import NewsItem
from news_scraper.settings import POSTGRES_SETTINGS


class IndonesiaInaNewsSpider(scrapy.Spider):
    name = "indonesia_ina_news"
    allowed_domains = ["ina.go.id", "www.ina.go.id"]
    start_urls = ["https://www.ina.go.id/ina-in-the-news/"]

    target_table = "idn_ina_news"
    default_cutoff = datetime(2026, 1, 1)

    custom_settings = {
        "DOWNLOAD_DELAY": 0.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 8,
    }

    def __init__(self, full_scan="false", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.full_scan = str(full_scan).lower() in ("1", "true", "yes")
        self.cutoff_date = self._init_db_and_get_cutoff()
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

            cur.execute(f"SELECT MAX(publish_time) FROM {self.target_table}")
            max_time = cur.fetchone()[0]
            cur.close()
            conn.close()

            if self.full_scan or not max_time:
                return self.default_cutoff
            return max(max_time, self.default_cutoff)
        except Exception as exc:
            self.logger.error(f"DB init failed: {exc}")
            return self.default_cutoff

    def parse(self, response):
        soup = BeautifulSoup(response.text, "html.parser")

        for card in soup.select("div.media-content_item"):
            anchor = card.select_one("a[href]")
            if not anchor:
                continue

            article_url = self._normalize_url(anchor.get("href", ""))
            if not article_url:
                continue
            if "/ina-in-the-news/" not in article_url:
                continue
            if article_url.rstrip("/") == "https://www.ina.go.id/ina-in-the-news":
                continue
            if article_url in self.seen_urls:
                continue
            self.seen_urls.add(article_url)

            title_node = card.select_one("h3.media-content_title")
            title = title_node.get_text(" ", strip=True) if title_node else ""

            date_node = card.select_one(".media-content_post-date")
            list_date = self._parse_datetime(date_node.get_text(" ", strip=True) if date_node else "")
            if list_date and list_date < self.cutoff_date:
                continue

            yield scrapy.Request(
                article_url,
                callback=self.parse_article,
                meta={
                    "title": title,
                    "list_date": list_date,
                },
            )

    def parse_article(self, response):
        soup = BeautifulSoup(response.text, "html.parser")

        title = self._extract_title(soup) or response.meta.get("title")
        if not title:
            return

        publish_time = self._extract_publish_time(soup) or response.meta.get("list_date")
        if publish_time and publish_time < self.cutoff_date:
            return

        content = self._extract_content(soup)
        if not content:
            return

        author = self._extract_author(soup) or "Indonesia Investment Authority"

        item = NewsItem()
        item["url"] = response.url
        item["title"] = title
        item["content"] = content
        item["publish_time"] = publish_time or datetime.now()
        item["author"] = author
        item["language"] = "en"
        item["section"] = "indonesia_ina_news"
        item["scrape_time"] = datetime.now()
        yield item

    def _normalize_url(self, url):
        cleaned = (url or "").replace("&amp;", "&").strip()
        cleaned = re.sub(r"\s+", "", cleaned)
        if cleaned.startswith("//"):
            return "https:" + cleaned
        if cleaned.startswith("/"):
            return "https://www.ina.go.id" + cleaned
        return cleaned

    def _extract_title(self, soup):
        node = soup.select_one(".blogpost1_title-wrapper h1")
        if node:
            return node.get_text(" ", strip=True)

        og_title = soup.select_one('meta[property="og:title"]')
        if og_title and og_title.get("content"):
            return og_title.get("content").strip()
        return ""

    def _extract_publish_time(self, soup):
        node = soup.select_one(".blogpost1_title-wrapper .text-size-small")
        if node:
            parsed = self._parse_datetime(node.get_text(" ", strip=True))
            if parsed:
                return parsed

        return None

    def _parse_datetime(self, text):
        value = (text or "").strip()
        if not value:
            return None

        for fmt in ("%B %d, %Y", "%b %d, %Y"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        return None

    def _extract_content(self, soup):
        paragraphs = []
        for p in soup.select(".blogpost1_content .text-lg p"):
            text = p.get_text(" ", strip=True)
            if not text:
                continue
            normalized = re.sub(r"\s+", " ", text)
            if len(normalized) < 20:
                continue
            paragraphs.append(normalized)

        if not paragraphs:
            container = soup.select_one(".blogpost1_content .text-lg")
            if container:
                text = container.get_text("\n", strip=True)
                text = re.sub(r"\n{2,}", "\n", text)
                return text.strip()
            return ""

        return "\n".join(paragraphs).strip()

    def _extract_author(self, soup):
        source_link = soup.select_one("a#source-link[href]")
        if not source_link:
            return ""

        href = source_link.get("href", "").strip()
        if not href:
            return ""

        parsed = urlparse(href)
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
