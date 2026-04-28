# 丹麦finance gov爬虫，负责抓取对应站点、机构或栏目内容。

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

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing)

    def parse_listing(self, response):
        html = self._fetch_html(self.start_urls[0])
        soup = BeautifulSoup(html, "html.parser")
        for link in soup.select("a[href]"):
            href = link.get("href")
            if not href or "/news/news/" not in href or href.rstrip("/") == "/news/news":
                continue
            full_url = response.urljoin(href)
            if not self.should_process(full_url):
                continue
            try:
                detail_html = self._fetch_html(full_url)
            except Exception:
                continue
            item = next(self.parse_detail(self._make_response(full_url, detail_html)), None)
            if item:
                yield item

    def parse_detail(self, response):
        title = self._clean_text(
            response.xpath("//meta[@property='og:title']/@content").get()
            or response.css("h1::text").get()
            or response.css("title::text").get()
        )
        if not title:
            return

        publish_time = self._extract_publish_time(response)
        if publish_time and not self.full_scan and publish_time < self.cutoff_date:
            return

        content = self._extract_content(response)
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
        text = self._clean_text(" ".join(response.css("main ::text").getall()[:80]))
        match = re.search(r"\b(\d{2}\.\d{2}\.\d{4})\b", text)
        if match:
            return self._parse_datetime(match.group(1), languages=["en"])
        return self._parse_datetime(text, languages=["en"])

    def _extract_content(self, response):
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
