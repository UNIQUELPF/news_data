# 芬兰stat爬虫，负责抓取对应站点、机构或栏目内容。
import re

from bs4 import BeautifulSoup

import scrapy

from news_scraper.spiders.finland.base import FinlandBaseSpider


class FinlandStatSpider(FinlandBaseSpider):
    name = "finland_stat"

    country_code = 'FIN'

    country = '芬兰'
    allowed_domains = ["stat.fi", "www.stat.fi"]
    start_urls = ["https://stat.fi/en"]

    # Listing page has no dates; check dates on detail pages
    strict_date_required = False

    async def start(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing, dont_filter=True)

    def parse_listing(self, response):
        seen = set()
        for link in response.css("a[href]"):
            href = (link.attrib.get("href") or "").strip()
            if not (href.startswith("/en/publication/") or href.startswith("/en/news/")):
                continue
            full_url = response.urljoin(href.split("?")[0])
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
        if not title:
            return

        publish_time = self._parse_datetime(
            response.xpath("//meta[@property='article:published_time']/@content").get()
            or response.xpath("//meta[@name='date']/@content").get()
            or self._find_date(response.text),
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
            author="Statistics Finland",
            language="en",
            section="statistics",
        )

    def _find_date(self, html):
        patterns = [
            r"\b\d{1,2}\s+[A-Z][a-z]+\s+\d{4}\b",
            r"\b[A-Z][a-z]+\s+\d{1,2},\s+\d{4}\b",
            r"\b\d{4}-\d{2}-\d{2}\b",
        ]
        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                return match.group(0)
        return ""

    def _do_extract_content(self, response):
        soup = BeautifulSoup(response.text, "html.parser")
        root = soup.select_one("main") or soup.select_one("article") or soup.select_one(".page-content")
        if not root:
            return ""
        for unwanted in root.select("script, style, nav, footer, header, aside, form, .share, .breadcrumbs"):
            unwanted.decompose()
        parts = []
        for node in root.find_all(["p", "li"], recursive=True):
            text = self._clean_text(node.get_text(" ", strip=True))
            if not text or len(text) < 35:
                continue
            if text.startswith("Search") or text.startswith("Go to content"):
                continue
            if text not in parts:
                parts.append(text)
        return "\n\n".join(parts)
