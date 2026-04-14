# 印度尼西亚kompas money爬虫，负责抓取对应站点、机构或栏目内容。

import re
from datetime import datetime
from urllib.parse import parse_qs, urlparse

import psycopg2
import scrapy
from bs4 import BeautifulSoup
from news_scraper.items import NewsItem
from news_scraper.settings import POSTGRES_SETTINGS
from news_scraper.utils import get_incremental_state


class IndonesiaKompasMoneySpider(scrapy.Spider):
    name = "indonesia_kompas_money"

    country_code = 'IDN'

    country = '印度尼西亚'
    allowed_domains = ["indeks.kompas.com", "money.kompas.com", "kompas.com"]
    start_urls = ["https://indeks.kompas.com/?site=money"]
    sitemap_urls = [
        "https://money.kompas.com/sitemap-archive-money.xml",
        "https://money.kompas.com/sitemap-news-money.xml",
        "https://money.kompas.com/sitemap-basic.xml",
    ]

    target_table = "idn_kompas_money"
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

    def parse(self, response):
        soup = BeautifulSoup(response.text, "html.parser")
        current_page = self._extract_current_page(response.url)

        page_links = soup.select("a.article-link[href]")
        if not page_links:
            return

        for anchor in page_links:
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

        next_page = self._find_next_page(soup, current_page)
        if next_page:
            yield scrapy.Request(next_page, callback=self.parse)

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse)

        for date_url in self._build_date_index_urls():
            yield scrapy.Request(date_url, callback=self.parse)

        for sitemap_url in self.sitemap_urls:
            yield scrapy.Request(sitemap_url, callback=self.parse_sitemap)

    def _build_date_index_urls(self):
        start_date = self.default_cutoff.date() if self.full_scan else self.cutoff_date.date()
        end_date = datetime.now().date()

        if start_date > end_date:
            return []

        urls = []
        current = start_date
        while current <= end_date:
            urls.append(f"https://indeks.kompas.com/?site=money&date={current.isoformat()}")
            current = current.fromordinal(current.toordinal() + 1)
        return urls

    def parse_sitemap(self, response):
        soup = BeautifulSoup(response.text, "xml")
        for url_node in soup.select("url"):
            loc_node = url_node.select_one("loc")
            if not loc_node:
                continue

            article_url = self._normalize_url(loc_node.get_text(strip=True))
            if not article_url or "money.kompas.com/read/" not in article_url:
                continue
            if article_url in self.seen_urls:
                continue
            self.seen_urls.add(article_url)

            list_date = self._extract_date_from_url(article_url)
            if list_date and list_date.date() < self.cutoff_date.date():
                continue

            yield scrapy.Request(
                article_url,
                callback=self.parse_article,
                meta={
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

        author = self._extract_author(soup)

        item = NewsItem()
        item["url"] = response.url
        item["title"] = title
        item["content"] = content
        item["publish_time"] = publish_time or datetime.now()
        item["author"] = author or "Kompas.com"
        item["language"] = "id"
        item["section"] = "indonesia_kompas_money"
        item["scrape_time"] = datetime.now()
        yield item

    def _extract_current_page(self, url):
        params = parse_qs(urlparse(url).query)
        value = params.get("page", ["1"])[0]
        try:
            return int(value)
        except (TypeError, ValueError):
            return 1

    def _find_next_page(self, soup, current_page):
        candidates = []
        for anchor in soup.select("a.paging__link[href]"):
            href = anchor.get("href", "")
            if "page=" not in href:
                continue
            page = self._extract_page_from_url(href)
            if page and page > current_page:
                candidates.append((page, href))

        if not candidates:
            return None

        next_page, next_href = sorted(candidates, key=lambda x: x[0])[0]
        if next_page != current_page + 1:
            return f"https://indeks.kompas.com/?site=money&page={current_page + 1}"
        return self._normalize_url(next_href)

    def _extract_page_from_url(self, url):
        params = parse_qs(urlparse(url).query)
        value = params.get("page", [None])[0]
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _normalize_url(self, url):
        cleaned = (url or "").replace("&amp;", "&").strip()
        cleaned = re.sub(r"\s+", "", cleaned)
        if cleaned.startswith("//"):
            return "https:" + cleaned
        if cleaned.startswith("/"):
            return "https://indeks.kompas.com" + cleaned
        return cleaned

    def _extract_date_from_url(self, url):
        match = re.search(r"/read/(\d{4})/(\d{2})/(\d{2})/", url)
        if not match:
            return None
        year, month, day = map(int, match.groups())
        try:
            return datetime(year, month, day)
        except ValueError:
            return None

    def _extract_title(self, soup):
        node = soup.select_one("h1.read__title")
        if node:
            return node.get_text(" ", strip=True)

        og_title = soup.select_one('meta[property="og:title"]')
        if og_title and og_title.get("content"):
            return og_title.get("content").strip()
        return ""

    def _extract_publish_time(self, soup):
        meta_date = soup.select_one('meta[name="content_PublishedDate"]')
        if meta_date and meta_date.get("content"):
            value = meta_date.get("content").strip()
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
                try:
                    return datetime.strptime(value, fmt)
                except ValueError:
                    continue

        time_node = soup.select_one(".read__time")
        if not time_node:
            return None

        text = time_node.get_text(" ", strip=True)
        match = re.search(
            r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})\s*,\s*(\d{1,2}):(\d{2})",
            text,
            flags=re.IGNORECASE,
        )
        if not match:
            return None

        month_map = {
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

        day = int(match.group(1))
        month_name = match.group(2).lower()
        year = int(match.group(3))
        hour = int(match.group(4))
        minute = int(match.group(5))
        month = month_map.get(month_name)
        if not month:
            return None

        try:
            return datetime(year, month, day, hour, minute)
        except ValueError:
            return None

    def _extract_content(self, soup):
        paragraphs = []
        for p in soup.select("div.read__content p"):
            text = p.get_text(" ", strip=True)
            if not text:
                continue

            normalized = re.sub(r"\s+", " ", text)
            lower = normalized.lower()
            if len(normalized) < 20:
                continue
            if lower.startswith("baca juga"):
                continue
            if lower.startswith("lihat foto"):
                continue
            if lower.startswith("simak breaking news"):
                continue
            if lower.startswith("dapatkan update berita"):
                continue
            paragraphs.append(normalized)

        if not paragraphs:
            container = soup.select_one("div.read__content")
            if not container:
                return ""
            text = container.get_text("\n", strip=True)
            return re.sub(r"\n{2,}", "\n", text).strip()

        return "\n".join(paragraphs).strip()

    def _extract_author(self, soup):
        meta_author = soup.select_one('meta[name="content_author"]')
        if meta_author and meta_author.get("content"):
            return meta_author.get("content").strip()

        node = soup.select_one("div.credit-title-name")
        if node:
            return node.get_text(" ", strip=True)

        fallback = soup.select_one('meta[name="author"]')
        if fallback and fallback.get("content"):
            return fallback.get("content").strip()
        return ""
