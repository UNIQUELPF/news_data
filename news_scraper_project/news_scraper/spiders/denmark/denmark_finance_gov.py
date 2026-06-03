# 丹麦finance gov爬虫，负责抓取对应站点、机构或栏目内容。
# en.fm.dk listing 页面无日期，需在详情页提取日期
import re

from bs4 import BeautifulSoup

import scrapy

from news_scraper.spiders.denmark.base import DenmarkBaseSpider


class DenmarkFinanceGovSpider(DenmarkBaseSpider):
    name = "denmark_finance_gov"

    country_code = 'DNK'

    country = '丹麦'
    allowed_domains = ["en.fm.dk", "fm.dk"]
    start_urls = ["https://en.fm.dk/news/news/"]

    # Listing page has no dates, we get dates on detail pages
    strict_date_required = False

    async def start(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing, dont_filter=True)

    def parse_listing(self, response):
        """
        Parse listing page: https://en.fm.dk/news/news/
        Links with /news/news/<slug> are article links. No date on listing page.
        """
        seen = set()
        for link in response.css("a[href]"):
            href = link.attrib.get("href", "")
            if not href or "/news/news/" not in href or href.rstrip("/") == "/news/news":
                continue
            full_url = response.urljoin(href)
            if full_url in seen:
                continue
            seen.add(full_url)
            # Don't filter by date at listing step — no date available
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

        publish_time = self._extract_publish_time(response)
        # Now apply date check on detail page
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
            author="Danish Ministry of Finance",
            language="en",
            section="finance",
        )

    def _extract_publish_time(self, response):
        # Look for DD.MM.YYYY in page text
        text = self._clean_text(" ".join(response.css("main ::text, article ::text").getall()[:120]))
        match = re.search(r"\b(\d{2}\.\d{2}\.\d{4})\b", text)
        if match:
            return self._parse_datetime(match.group(1), languages=["en"])
        # Also try meta date
        meta_date = response.xpath("//meta[@name='date']/@content").get() or \
                    response.xpath("//meta[@property='article:published_time']/@content").get()
        if meta_date:
            return self._parse_datetime(meta_date, languages=["en"])
        return None

    def _do_extract_content(self, response):
        soup = BeautifulSoup(response.text, "html.parser")
        root = soup.select_one("main")
        if not root:
            return ""
        for unwanted in root.select("script, style, nav, footer, header, aside, form"):
            unwanted.decompose()
        parts = []
        for node in root.find_all(["p", "li"], recursive=True):
            text = self._clean_text(node.get_text(" ", strip=True))
            if not text or len(text) < 35:
                continue
            if text == "News":
                continue
            if text not in parts:
                parts.append(text)
        return "\n\n".join(parts)
