# 德国bundesbank爬虫，负责抓取对应站点、机构或栏目内容。

import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

import scrapy

from news_scraper.spiders.germany.base import GermanyBaseSpider


class GermanyBundesbankSpider(GermanyBaseSpider):
    name = "germany_bundesbank"

    country_code = 'DEU'

    country = '德国'
    allowed_domains = ["bundesbank.de", "www.bundesbank.de"]
    target_table = "deu_bundesbank"
    start_urls = ["https://www.bundesbank.de/en/press/press-releases"]

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing)

    def parse_listing(self, response):
        html = self._fetch_html(self.start_urls[0])
        soup = BeautifulSoup(html, "html.parser")
        for link in soup.select("a[href]"):
            href = link.get("href") or ""
            if "/en/press/press-releases/" not in href:
                continue
            if href.rstrip("/").endswith("/press-releases"):
                continue
            full_url = response.urljoin(href.split("?")[0])
            parsed = urlparse(full_url)
            slug = parsed.path.rstrip("/").split("/")[-1]
            if not re.search(r"-\d+$", slug):
                continue
            if full_url in self.seen_urls:
                continue
            self.seen_urls.add(full_url)
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

        publish_time = self._parse_datetime(
            self._clean_text(
                response.css(".metadata__date::text").get()
                or response.xpath("//meta[contains(@property,'published')]/@content").get()
            ),
            languages=["de", "en"],
        )
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
            author="Deutsche Bundesbank",
            language="en",
            section="central_bank",
        )

    def _extract_content(self, response):
        soup = BeautifulSoup(response.text, "html.parser")
        root = soup.select_one(".richtext") or soup.select_one("main")
        if not root:
            return ""
        for unwanted in root.select("script, style, nav, footer, header, aside, form"):
            unwanted.decompose()
        parts = []
        for node in root.find_all(["p", "li"], recursive=True):
            text = self._clean_text(node.get_text(" ", strip=True))
            if not text or len(text) < 35:
                continue
            if text.startswith("Contact") or text.startswith("Download"):
                continue
            if text not in parts:
                parts.append(text)
        return "\n\n".join(parts)

