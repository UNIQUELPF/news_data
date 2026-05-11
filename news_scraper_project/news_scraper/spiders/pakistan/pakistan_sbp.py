# 巴基斯坦sbp爬虫，负责抓取对应站点、机构或栏目内容。

import re
from datetime import datetime

import scrapy
from scrapy_playwright.page import PageMethod

from news_scraper.spiders.pakistan.base import PakistanBaseSpider


class PakistanSbpSpider(PakistanBaseSpider):
    name = "pakistan_sbp"

    country_code = 'PAK'

    playwright = True

    country = '巴基斯坦'
    allowed_domains = ["sbp.org.pk", "www.sbp.org.pk"]
    target_table = "pak_sbp"
    start_urls = [
        "https://www.sbp.org.pk/press/releases.asp",
    ]

    custom_settings = {
        "DOWNLOAD_DELAY": 0.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
    }

    async def start(self):
        self._stop_pagination = False
        for url in self.start_urls:
            yield scrapy.Request(
                url,
                callback=self.parse_listing,
                meta={
                    "playwright": True,
                    "playwright_context": "pakistan_sbp",
                    "playwright_page_methods": [
                        PageMethod("wait_for_function", "() => document.title !== 'Just a moment...'", timeout=30000),
                    ],
                },
                dont_filter=True,
            )

    def parse_listing(self, response):
        min_year = self.cutoff_date.year
        has_valid_item_in_window = self.full_scan
        for href in response.css("a::attr(href)").getall():
            if self._stop_pagination:
                break
            full_url = response.urljoin(href)
            match = re.search(r"/press/(20\d{2})/index\d*\.asp$", full_url, re.IGNORECASE)
            if not match:
                continue
            year = int(match.group(1))
            if year < min_year:
                if not has_valid_item_in_window:
                    break
                continue
            if not self.full_scan and full_url in self.seen_urls:
                continue
            self.seen_urls.add(full_url)
            has_valid_item_in_window = True
            yield scrapy.Request(
                full_url,
                callback=self.parse_year_page,
                meta={
                    "playwright": True,
                    "playwright_context": "pakistan_sbp",
                },
                dont_filter=self.full_scan,
            )

    def _extract_date_from_text(self, text):
        """Extract date from PDF URL like Pr-28-Apr-2026.pdf or title like Monetary Policy Statement(27-Apr-2026).
        Falls back to dateparser if regex doesn't match."""
        if not text:
            return None
        # Regex for DD-Mon-YYYY pattern (e.g., 28-Apr-2026, 27-Apr-2026)
        match = re.search(r'(\d{1,2}-[A-Za-z]{3}-\d{4})', text)
        if match:
            try:
                return datetime.strptime(match.group(1), "%d-%b-%Y")
            except ValueError:
                pass
        return self._parse_datetime(text, languages=["en"])

    def parse_year_page(self, response):
        for link in response.css("a[href$='.pdf']"):
            if self._stop_pagination:
                break
            href = link.attrib.get("href")
            if not href:
                continue

            full_url = response.urljoin(href)
            if not self.full_scan and full_url in self.seen_urls:
                continue
            self.seen_urls.add(full_url)

            title = self._clean_text(link.xpath("normalize-space()").get())
            if not title or title.lower() == "click here":
                continue

            publish_time = self._extract_date_from_text(title)
            if not publish_time:
                publish_time = self._extract_date_from_text(full_url)
            if publish_time and publish_time < self.cutoff_date:
                self._stop_pagination = True
                continue
            yield scrapy.Request(
                full_url,
                callback=self.parse_pdf,
                cb_kwargs={"title": title, "publish_time": publish_time},
                meta={
                    "playwright": True,
                    "playwright_context": "pakistan_sbp",
                },
                dont_filter=self.full_scan,
            )

    def parse_pdf(self, response, title, publish_time):
        content = self._extract_pdf_text(response.body)
        if not content:
            content = title

        yield {
            "title": title,
            "content": content,
            "publish_time": publish_time,
            "url": response.url,
            "source_country": "Pakistan",
            "source_name": "State Bank of Pakistan",
            "language": "en",
            "author": "State Bank of Pakistan",
            "section": "press",
        }
