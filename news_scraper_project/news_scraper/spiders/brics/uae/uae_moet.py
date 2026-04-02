# 阿联酋moet爬虫，负责抓取对应站点、机构或栏目内容。

import re
from datetime import datetime

import psycopg2
import scrapy
from bs4 import BeautifulSoup

from news_scraper.items import NewsItem
from news_scraper.settings import POSTGRES_SETTINGS


class UaeMoetSpider(scrapy.Spider):
    name = "uae_moet"
    allowed_domains = ["moet.gov.ae"]
    start_urls = ["https://www.moet.gov.ae/en/news"]

    target_table = "uae_moet"
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
        self.page_url_template = None
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
            return max_time
        except Exception as exc:
            self.logger.error(f"DB init failed: {exc}")
            return self.default_cutoff

    def parse(self, response):
        soup = BeautifulSoup(response.text, "html.parser")

        current_page = self._extract_current_page(response.url)
        if self.page_url_template is None:
            self.page_url_template = self._extract_page_url_template(soup)
        if self.total_pages is None:
            self.total_pages = self._extract_total_pages(soup)

        cards = soup.select("div.item.custom_animation")
        for card in cards:
            article_url = self._extract_article_url(card)
            if not article_url:
                continue
            if article_url in self.seen_urls:
                continue
            self.seen_urls.add(article_url)

            title = self._extract_list_title(card)
            publish_time = self._extract_list_date(card)

            if publish_time and publish_time < self.cutoff_date:
                self.reached_cutoff = True
                continue

            yield scrapy.Request(
                article_url,
                callback=self.parse_article,
                meta={
                    "title": title,
                    "publish_time": publish_time,
                },
            )

        if self.reached_cutoff:
            return

        if self.page_url_template and self.total_pages and current_page < self.total_pages:
            next_page = current_page + 1
            next_url = self.page_url_template.format(next_page)
            yield scrapy.Request(next_url, callback=self.parse)

    def parse_article(self, response):
        soup = BeautifulSoup(response.text, "html.parser")

        title = response.meta.get("title") or self._extract_detail_title(soup)
        if not title:
            return

        publish_time = response.meta.get("publish_time") or self._extract_detail_date(soup)
        if publish_time and publish_time < self.cutoff_date:
            return

        content = self._extract_detail_content(soup, title)
        if not content:
            return

        item = NewsItem()
        item["url"] = response.url
        item["title"] = title
        item["content"] = content
        item["publish_time"] = publish_time or datetime.now()
        item["author"] = "MOET"
        item["language"] = "en"
        item["section"] = "uae_moet"
        item["scrape_time"] = datetime.now()
        yield item

    def _extract_current_page(self, url):
        match = re.search(r"_cur=(\d+)", url)
        if match:
            return int(match.group(1))
        return 1

    def _extract_page_url_template(self, soup):
        for a in soup.select("ul.pagination a.page-link[href]"):
            href = a.get("href")
            if not href or "_cur=" not in href:
                continue
            normalized = href.replace("&amp;", "&")
            match = re.search(r"(.*_cur=)\d+", normalized)
            if match:
                return match.group(1) + "{}"
        return None

    def _extract_total_pages(self, soup):
        result_text = ""
        p = soup.select_one("p.pagination-results")
        if p:
            result_text = p.get_text(" ", strip=True)

        total_entries = None
        if result_text:
            m = re.search(r"of\s+(\d+)\s+entries", result_text, flags=re.IGNORECASE)
            if m:
                total_entries = int(m.group(1))

        delta = 12
        for a in soup.select("ul.pagination a.page-link[href]"):
            href = a.get("href")
            if not href:
                continue
            m = re.search(r"_delta=(\d+)", href)
            if m:
                delta = int(m.group(1))
                break

        if total_entries and delta > 0:
            return (total_entries + delta - 1) // delta

        page_numbers = []
        for a in soup.select("ul.pagination a.page-link[href]"):
            txt = a.get_text(" ", strip=True)
            if txt.isdigit():
                page_numbers.append(int(txt))
        return max(page_numbers) if page_numbers else 1

    def _extract_article_url(self, card):
        for a in card.select("a[href]"):
            href = a.get("href")
            if href and "/en/-/" in href:
                return response_url_join("https://www.moet.gov.ae", href)
        return None

    def _extract_list_title(self, card):
        title_node = card.select_one("div.head_line p, div.head_line a")
        if title_node:
            return title_node.get_text(" ", strip=True)
        return ""

    def _extract_list_date(self, card):
        date_node = card.select_one("div.date")
        if not date_node:
            return None
        return self._parse_date(date_node.get_text(" ", strip=True))

    def _extract_detail_title(self, soup):
        og_title = soup.select_one('meta[property="og:title"]')
        if og_title and og_title.get("content"):
            content = og_title.get("content").strip()
            return re.sub(r"\s*-\s*Ministry of Economy.*$", "", content).strip()

        journal_first = soup.select_one("div.news_detail.custom_animation.content_area p")
        if journal_first:
            return journal_first.get_text(" ", strip=True)
        return ""

    def _extract_detail_date(self, soup):
        date_node = soup.select_one("div.date")
        if date_node:
            return self._parse_date(date_node.get_text(" ", strip=True))
        return None

    def _extract_detail_content(self, soup, title):
        container = soup.select_one("div.news_detail.custom_animation.content_area")
        if not container:
            return ""

        paragraphs = []
        for p in container.select("p"):
            text = p.get_text(" ", strip=True)
            if text:
                paragraphs.append(text)

        if not paragraphs:
            text = container.get_text("\n", strip=True)
            return text.strip()

        normalized_title = re.sub(r"\s+", " ", title).strip().lower()
        if paragraphs:
            normalized_first = re.sub(r"\s+", " ", paragraphs[0]).strip().lower()
            if normalized_first == normalized_title:
                paragraphs = paragraphs[1:]

        paragraphs = [p for p in paragraphs if len(p) > 20]
        return "\n".join(paragraphs).strip()

    def _parse_date(self, text):
        if not text:
            return None
        value = re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()
        value = re.sub(r"^(Published on|Date)\s*:?\s*", "", value, flags=re.IGNORECASE)
        for fmt in ("%d %b %Y", "%d %B %Y"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        return None


def response_url_join(base_url, maybe_relative_url):
    if maybe_relative_url.startswith("http://") or maybe_relative_url.startswith("https://"):
        return maybe_relative_url
    return base_url.rstrip("/") + "/" + maybe_relative_url.lstrip("/")
