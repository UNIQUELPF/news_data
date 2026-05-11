# 德国bafin爬虫，负责抓取对应站点、机构或栏目内容。

import re

from bs4 import BeautifulSoup

import scrapy

from news_scraper.spiders.germany.base import GermanyBaseSpider


class GermanyBafinSpider(GermanyBaseSpider):
    name = "germany_bafin"

    country_code = 'DEU'

    country = '德国'
    allowed_domains = ["bafin.de", "www.bafin.de"]

    fallback_content_selector = "#content, main, article"

    start_urls = [
        "https://www.bafin.de/EN/die-bafin/aktuelles-presse/presse-social-media/pressemitteilungen/pressemitteilungen_node_en.html",
    ]

    async def start(self):
        self._stop_pagination = False
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing, dont_filter=True)

    def parse_listing(self, response):
        if self._stop_pagination:
            return

        soup = BeautifulSoup(response.text, "html.parser")

        has_valid_item_in_window = self.full_scan

        for link in soup.select("a[href]"):
            if self._stop_pagination:
                break
            href = link.get("href") or ""
            if "SharedDocs/Veroeffentlichungen/EN/Pressemitteilung/" not in href:
                continue
            full_url = response.urljoin(href.split(";")[0].split("?")[0])
            if not self.should_process(full_url):
                continue

            has_valid_item_in_window = True
            yield scrapy.Request(full_url, callback=self.parse_detail, dont_filter=self.full_scan)

        if not has_valid_item_in_window:
            self._stop_pagination = True

    def parse_detail(self, response):
        title = self._clean_text(
            response.xpath("//meta[@property='og:title']/@content").get()
            or response.css("h1::text").get()
            or response.css("title::text").get()
        )
        if not title:
            return

        publish_time = self._parse_datetime(
            response.css("span.c-topline__element::text").get()
            or response.xpath("//meta[@property='article:published_time']/@content").get()
            or response.xpath("//time/@datetime").get()
            or " ".join(response.xpath("//div[@id='content']//text()").getall()[:80]),
            languages=["de", "en"],
        )
        if not self.should_process(response.url, publish_time):
            self._stop_pagination = True
            return

        content = self._extract_content(response)
        if not content:
            return

        yield self._build_item(
            response=response,
            title=title,
            content=content,
            publish_time=publish_time,
            author="BaFin",
            language="en",
            section="financial_regulation",
        )

    def _extract_content(self, response):
        soup = BeautifulSoup(response.text, "html.parser")
        # Prefer main over #content to avoid breadcrumbs in the extracted content
        root = soup.select_one("main") or soup.select_one("#content") or soup.select_one("article")
        if not root:
            return ""
        for unwanted in root.select(
            "script, style, nav, footer, header, aside, form, "
            ".wrapperRating, .sectionRelated, "
            ".l-article__related, .l-article__author, .l-content-breadcrumb, .c-intro, "
            ".c-related, .c-teaser-contact"
        ):
            unwanted.decompose()
        parts = []
        for node in root.find_all(["p", "li"], recursive=True):
            text = self._clean_text(node.get_text(" ", strip=True))
            if not text or len(text) < 35:
                continue
            if text.startswith("Did you find this article helpful") or text.startswith("Mandatory field"):
                continue
            if text not in parts:
                parts.append(text)
        return "\n\n".join(parts)
