# 芬兰finanssivalvonta爬虫，负责抓取对应站点、机构或栏目内容。
from bs4 import BeautifulSoup

import scrapy

from news_scraper.spiders.finland.base import FinlandBaseSpider


class FinlandFinanssivalvontaSpider(FinlandBaseSpider):
    name = "finland_finanssivalvonta"

    country_code = 'FIN'

    country = '芬兰'
    allowed_domains = ["finanssivalvonta.fi", "www.finanssivalvonta.fi"]
    fallback_content_selector = "main, article, .page-content"
    start_urls = [
        "https://www.finanssivalvonta.fi/en/publications-and-press-releases/news-releases/2025/",
        "https://www.finanssivalvonta.fi/en/publications-and-press-releases/news-releases/2026/",
    ]

    # Listing page links have no separate date elements; date is extracted from detail pages
    strict_date_required = False

    async def start(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing, dont_filter=True)

    def parse_listing(self, response):
        """
        Parse listing pages for Finnish FSA press releases (2025 and 2026 year pages).
        Each link like /en/publications-and-press-releases/news-releases/2025/slug/
        """
        seen = set()
        for link in response.css("a[href]"):
            href = (link.attrib.get("href") or "").strip()
            if not href.startswith("/en/publications-and-press-releases/news-releases/"):
                continue
            if href.endswith("/2025/") or href.endswith("/2026/") or href.endswith("/news-releases/"):
                continue
            if href.count("/") < 6:
                continue
            full_url = response.urljoin(href.split("?")[0].rstrip("/") + "/")
            if full_url in seen:
                continue
            seen.add(full_url)
            if not self.should_process(full_url, None):
                continue
            yield scrapy.Request(full_url, callback=self.parse_detail)

    def parse_detail(self, response):
        title = self._clean_text(
            response.xpath("//meta[@property='og:title']/@content").get()
            or response.css("h1::text").get()
            or response.css("title::text").get()
        )
        if not title or title == "Sivua ei löytynyt":
            return

        publish_time = self._parse_datetime(
            response.xpath("//meta[@property='article:published_time']/@content").get()
            or self._clean_text(" ".join(response.css("body ::text").getall()[:120])),
            languages=["en"],
        )
        if not self.should_process(response.url, publish_time):
            return

        content = self._do_extract_content(response)
        if not content:
            return

        yield self._build_item(
            response=response,
            title=title,
            content=content,
            publish_time=publish_time,
            author="FIN-FSA",
            language="en",
            section="financial_regulator",
        )

    def _do_extract_content(self, response):
        soup = BeautifulSoup(response.text, "html.parser")
        root = soup.select_one("main") or soup.select_one("article") or soup.select_one(".page-content")
        if not root:
            return ""
        for unwanted in root.select("script, style, nav, footer, header, aside, form, .share, .subnavigation"):
            unwanted.decompose()
        parts = []
        for node in root.find_all(["p", "li"], recursive=True):
            text = self._clean_text(node.get_text(" ", strip=True))
            if not text or len(text) < 35:
                continue
            if text.startswith("Go to content") or text.startswith("Published"):
                continue
            if text not in parts:
                parts.append(text)
        return "\n\n".join(parts)
