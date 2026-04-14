# 澳大利亚asic爬虫，负责抓取对应站点、机构或栏目内容。

import json
from datetime import datetime

from bs4 import BeautifulSoup

import scrapy

from news_scraper.spiders.australia.base import AustraliaBaseSpider


class AustraliaAsicSpider(AustraliaBaseSpider):
    name = "australia_asic"

    country_code = 'AUS'

    country = '澳大利亚'
    allowed_domains = ["asic.gov.au", "www.asic.gov.au"]
    target_table = "aus_asic"
    start_urls = [
        "https://www.asic.gov.au/_data/mr2023/",
    ]

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing)
        if self.full_scan or self.cutoff_date < datetime(2025, 1, 1):
            yield scrapy.Request(
                "https://download.asic.gov.au/scripts/newsroom/mr-archive.json",
                callback=self.parse_listing,
            )

    def parse_listing(self, response):
        try:
            payload = json.loads(response.text)
        except Exception:
            payload = []

        if isinstance(payload, dict):
            payload = payload.get("items") or payload.get("data") or []

        for entry in payload:
            if not isinstance(entry, dict):
                continue
            full_url = entry.get("url")
            if not full_url:
                continue
            if full_url.startswith("/"):
                full_url = response.urljoin(full_url)
            if full_url in self.seen_urls:
                continue
            meta_type = self._clean_text(entry.get("metaType")).lower()
            if meta_type and meta_type != "media release":
                continue
            if "/find-a-media-release/" not in full_url and "/newsroom/" not in full_url:
                continue
            publish_time = self._extract_listing_publish_time(entry)
            if publish_time and not self.full_scan and publish_time < self.cutoff_date:
                continue
            self.seen_urls.add(full_url)
            yield scrapy.Request(full_url, callback=self.parse_detail)

    def parse_detail(self, response):
        title = self._clean_text(
            response.xpath("//meta[@property='og:title']/@content").get()
            or response.css("h1::text").get()
        )
        if not title:
            return

        publish_time = self._parse_datetime(
            response.xpath("//meta[@property='article:published_time']/@content").get()
            or response.css("time::attr(datetime), time::text").get()
            or response.xpath("//meta[@name='dcterms.date.created']/@content").get()
            or response.xpath("//meta[@name='dcterms.date.modified']/@content").get()
            or response.css(".publish-date::text").get(),
            languages=["en"],
        )
        if publish_time and not self.full_scan and publish_time < self.cutoff_date:
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
            author="ASIC",
            language="en",
            section="media-release",
        )

    def _extract_content(self, response, title):
        soup = BeautifulSoup(response.text, "html.parser")
        root = soup.select_one("main") or soup.select_one("article") or soup.select_one("#content")
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

    def _extract_listing_publish_time(self, entry):
        return self._parse_datetime(
            entry.get("publishedDate") or entry.get("dateCreated") or entry.get("createDate"),
            languages=["en"],
        )
