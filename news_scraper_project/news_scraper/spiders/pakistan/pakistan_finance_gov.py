# 巴基斯坦finance gov爬虫，负责抓取对应站点、机构或栏目内容。

import re
from datetime import datetime

from bs4 import BeautifulSoup

import scrapy

from news_scraper.spiders.pakistan.base import PakistanBaseSpider


class PakistanFinanceGovSpider(PakistanBaseSpider):
    name = "pakistan_finance_gov"

    country_code = 'PAK'

    country = '巴基斯坦'
    allowed_domains = ["finance.gov.pk", "www.finance.gov.pk"]
    target_table = "pak_finance_gov"

    fallback_content_selector = "article, main"

    start_urls = [
        "https://www.finance.gov.pk/press_releases.html",
        "https://www.finance.gov.pk/updates.html",
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._stop_pagination = False

    def _extract_date_from_text(self, text):
        """Extract date from PDF URL like Pr-28-Apr-2026.pdf or title with date in parentheses.
        Falls back to dateparser if regex doesn't match."""
        if not text:
            return None
        match = re.search(r'(\d{1,2}-[A-Za-z]{3}-\d{4})', text)
        if match:
            try:
                return datetime.strptime(match.group(1), "%d-%b-%Y")
            except ValueError:
                pass
        return self._parse_datetime(text, languages=["en"])

    def should_process(self, url, publish_time=None):
        if self.full_scan:
            return True
        if publish_time and publish_time < self.cutoff_date:
            return False
        return url not in self.seen_urls

    async def start(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing, dont_filter=True)

    def parse_listing(self, response):
        if self._stop_pagination:
            return
        has_valid_item_in_window = False
        for link in response.css("a[href]"):
            href = link.attrib.get("href")
            title = self._clean_text(link.xpath("normalize-space()").get())
            if not href:
                continue
            full_url = response.urljoin(href)
            if full_url in self.seen_urls:
                continue
            if "finance.gov.pk" not in full_url:
                continue
            lower_url = full_url.lower()
            if (
                "/press/" not in lower_url
                and "/economic/" not in lower_url
                and "press_releases" not in lower_url
                and "updates.html" not in lower_url
            ):
                continue
            self.seen_urls.add(full_url)
            if lower_url.endswith(".pdf"):
                item_title = title or full_url.rsplit("/", 1)[-1]
                publish_time = self._extract_date_from_text(item_title)
                if not publish_time:
                    publish_time = self._extract_date_from_text(full_url)
                if publish_time and publish_time < self.cutoff_date:
                    continue
                has_valid_item_in_window = True
                yield scrapy.Request(
                    full_url,
                    callback=self.parse_pdf,
                    cb_kwargs={"title": item_title, "publish_time": publish_time},
                )
                continue

            if lower_url.endswith((".xls", ".xlsx", ".doc", ".docx", ".zip")):
                continue

            has_valid_item_in_window = True
            yield scrapy.Request(full_url, callback=self.parse_detail)
        if not has_valid_item_in_window:
            self._stop_pagination = True

    def parse_detail(self, response):
        if not hasattr(response, "text"):
            return

        title = self._clean_text(
            response.xpath("//meta[@property='og:title']/@content").get()
            or response.css("h1::text").get()
            or response.css("title::text").get()
        )
        if not title:
            return

        publish_time = self._parse_datetime(
            response.xpath("//meta[@property='article:published_time']/@content").get()
            or response.css("time::attr(datetime), time::text").get()
            or response.xpath("//text()[contains(., 'Date')]/following::text()[1]").get(),
            languages=["en"],
        )
        if not self.should_process(response.url, publish_time):
            self._stop_pagination = True
            return

        content = self._extract_content(response, title)
        if not content:
            content = self._clean_text(response.xpath("//meta[@name='description']/@content").get())
        if not content:
            return

        yield self._build_item(
            response=response,
            title=title,
            content=content,
            publish_time=publish_time,
            author="Ministry of Finance Pakistan",
            language="en",
            section="government",
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
            "source_name": "Ministry of Finance Pakistan",
            "language": "en",
            "author": "Ministry of Finance Pakistan",
            "section": "government",
        }

    def _extract_content(self, response, title):
        soup = BeautifulSoup(response.text, "html.parser")
        root = soup.select_one("article") or soup.select_one("main") or soup.select_one("#content")
        if not root:
            return ""

        for unwanted in root.select("script, style, nav, footer, header, aside, form, .share, .related"):
            unwanted.decompose()

        title_text = self._clean_text(title)
        parts = []
        for node in root.find_all(["p", "h2", "h3", "li"], recursive=True):
            text = self._clean_text(node.get_text(" ", strip=True))
            if not text or len(text) < 25 or text == title_text:
                continue
            if text not in parts:
                parts.append(text)
        return "\n\n".join(parts)
