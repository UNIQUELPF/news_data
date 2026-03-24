import re
from datetime import datetime
from urllib.parse import parse_qs, urlparse

import psycopg2
import scrapy
from bs4 import BeautifulSoup

from news_scraper.items import NewsItem
from news_scraper.settings import POSTGRES_SETTINGS


class IndonesiaBisnisSpider(scrapy.Spider):
    name = "indonesia_bisnis"
    allowed_domains = ["bisnis.com", "ekonomi.bisnis.com"]
    start_urls = ["https://www.bisnis.com/index?categoryId=43"]

    target_table = "idn_bisnis"
    default_cutoff = datetime(2026, 1, 1)

    custom_settings = {
        "DOWNLOAD_DELAY": 0.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 8,
    }

    MONTH_MAP = {
        "januari": 1,
        "februari": 2,
        "maret": 3,
        "april": 4,
        "mei": 5,
        "juni": 6,
        "juli": 7,
        "agustus": 8,
        "september": 9,
        "oktober": 10,
        "november": 11,
        "desember": 12,
    }

    def __init__(self, full_scan="false", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.full_scan = str(full_scan).lower() in ("1", "true", "yes")
        self.cutoff_date = self._init_db_and_get_cutoff()
        self.reached_cutoff = False
        self.seen_urls = set()
        self.total_pages = None

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

        if self.total_pages is None:
            self.total_pages = self._extract_total_pages(soup)

        current_page = self._extract_current_page(response.url)

        for anchor in soup.select("a.artLink[href]"):
            article_url = self._normalize_url(anchor.get("href", ""))
            if not article_url or "/read/" not in article_url:
                continue
            if article_url in self.seen_urls:
                continue
            self.seen_urls.add(article_url)

            list_date = self._extract_date_from_url(article_url)
            if list_date and list_date.date() < self.cutoff_date.date():
                self.reached_cutoff = True
                continue

            title = anchor.get_text(" ", strip=True)
            yield scrapy.Request(
                article_url,
                callback=self.parse_article,
                meta={
                    "title": title,
                    "list_date": list_date,
                },
            )

        if self.reached_cutoff:
            return

        if self.total_pages and current_page < self.total_pages:
            next_page = current_page + 1
            next_url = f"https://www.bisnis.com/index?categoryId=43&page={next_page}"
            yield scrapy.Request(next_url, callback=self.parse)

    def parse_article(self, response):
        soup = BeautifulSoup(response.text, "html.parser")

        title = response.meta.get("title") or self._extract_title(soup)
        if not title:
            return

        publish_time = self._extract_publish_time(soup) or response.meta.get("list_date")
        if publish_time and publish_time < self.cutoff_date:
            return

        content = self._extract_content(soup)
        if not content:
            return

        author = self._extract_author(soup)

        item = NewsItem()
        item["url"] = response.url
        item["title"] = title
        item["content"] = content
        item["publish_time"] = publish_time or datetime.now()
        item["author"] = author or "Bisnis.com"
        item["language"] = "id"
        item["section"] = "indonesia_bisnis"
        item["scrape_time"] = datetime.now()
        yield item

    def _extract_total_pages(self, soup):
        total_node = soup.select_one("input#total_page")
        if total_node and total_node.get("value", "").isdigit():
            return int(total_node.get("value"))

        page_numbers = []
        for anchor in soup.select("ol.pagingList a[href]"):
            href = anchor.get("href", "")
            match = re.search(r"[?&]page=(\d+)", href)
            if match:
                page_numbers.append(int(match.group(1)))
        return max(page_numbers) if page_numbers else 1

    def _extract_current_page(self, url):
        params = parse_qs(urlparse(url).query)
        page = params.get("page", ["1"])[0]
        try:
            return int(page)
        except (TypeError, ValueError):
            return 1

    def _normalize_url(self, url):
        cleaned = re.sub(r"\s+", "", (url or "")).replace("&amp;", "&")
        if cleaned.startswith("//"):
            return "https:" + cleaned
        if cleaned.startswith("/"):
            return "https://www.bisnis.com" + cleaned
        return cleaned

    def _extract_date_from_url(self, url):
        match = re.search(r"/read/(\d{4})(\d{2})(\d{2})/", url)
        if not match:
            return None
        year, month, day = map(int, match.groups())
        try:
            return datetime(year, month, day)
        except ValueError:
            return None

    def _extract_title(self, soup):
        node = soup.select_one("h1.detailsTitleCaption")
        if node:
            return node.get_text(" ", strip=True)

        meta_title = soup.select_one('meta[property="og:title"]')
        if meta_title and meta_title.get("content"):
            return meta_title.get("content").strip()
        return ""

    def _extract_publish_time(self, soup):
        node = soup.select_one(".detailsAttributeDates")
        if not node:
            return None

        text = node.get_text(" ", strip=True)
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"^[^,]+,\s*", "", text)

        match = re.search(
            r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})(?:\s*\|\s*(\d{1,2}):(\d{2}))?",
            text,
        )
        if not match:
            return None

        day = int(match.group(1))
        month_name = match.group(2).lower()
        year = int(match.group(3))
        hour = int(match.group(4) or 0)
        minute = int(match.group(5) or 0)

        month = self.MONTH_MAP.get(month_name)
        if not month:
            return None

        try:
            return datetime(year, month, day, hour, minute)
        except ValueError:
            return None

    def _extract_content(self, soup):
        paragraphs = []
        for p in soup.select(".detailsContent p"):
            text = p.get_text(" ", strip=True)
            if not text:
                continue
            if len(text) < 20:
                continue
            if text.lower().startswith("cek berita"):
                continue
            paragraphs.append(text)

        if not paragraphs:
            container = soup.select_one(".detailsContent")
            if not container:
                return ""
            text = container.get_text("\n", strip=True)
            return re.sub(r"\n{2,}", "\n", text).strip()

        return "\n".join(paragraphs).strip()

    def _extract_author(self, soup):
        node = soup.select_one(".detailsAttributeAuthor a, .detailsAuthor a")
        if node:
            return node.get_text(" ", strip=True)

        fallback = soup.select_one(".detailsAttributeAuthor, .detailsAuthor")
        if fallback:
            text = fallback.get_text(" ", strip=True)
            text = re.sub(r"\s+", " ", text)
            text = re.sub(r"^Penulis\s*:\s*", "", text, flags=re.IGNORECASE)
            return text.strip()
        return ""
