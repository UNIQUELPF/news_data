# 丹麦finanstilsynet爬虫，负责抓取对应站点、机构或栏目内容。
import html
import json
import re

from bs4 import BeautifulSoup

import scrapy

from news_scraper.spiders.denmark.base import DenmarkBaseSpider


class DenmarkFinanstilsynetSpider(DenmarkBaseSpider):
    name = "denmark_finanstilsynet"

    country_code = 'DNK'

    country = '丹麦'
    allowed_domains = ["finanstilsynet.dk", "www.finanstilsynet.dk"]
    start_urls = ["https://www.finanstilsynet.dk/nyheder-og-presse/nyheder-og-pressemeddelelser"]

    async def start(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing, dont_filter=True)

    def parse_listing(self, response):
        """
        Parse listing page using the dynamic API endpoint.
        """
        html_text = response.text
        config = self._extract_dynamic_config(html_text)
        if not config:
            self.logger.warning("Could not extract dynamic config from finanstilsynet listing page")
            return

        payload = {
            "config": config,
            "page": 1,
            "userInput": {},
            "lastGroupName": None,
            "rootFolders": None,
        }
        headers = {
            "Content-Type": "application/json",
            "Referer": self.start_urls[0],
            "Origin": "https://www.finanstilsynet.dk",
        }

        try:
            result = json.loads(
                self._fetch_html(
                    "https://www.finanstilsynet.dk/gbapi/search/getPage",
                    method="POST",
                    json_data=payload,
                    headers=headers,
                )
            )
        except Exception as e:
            self.logger.warning(f"Failed to fetch finanstilsynet API: {e}")
            return

        page_html = result.get("pageHtml", "")
        soup = BeautifulSoup(page_html, "html.parser")
        for card in soup.select(".item"):
            link = card.select_one("a[href]")
            if not link:
                continue
            full_url = link.get("href")
            if not full_url:
                continue

            publish_time = None
            date_node = card.select_one("[data-date]")
            if date_node:
                publish_time = self._parse_datetime(date_node.get("data-date"), languages=["da", "en"])

            if not self.should_process(full_url, publish_time):
                continue

            yield scrapy.Request(
                full_url,
                callback=self.parse_detail,
                meta={"publish_time": publish_time},
            )

    def parse_detail(self, response):
        publish_time = response.meta.get("publish_time")

        title = self._clean_text(
            response.xpath("//meta[@property='og:title']/@content").get()
            or response.css("h1::text").get()
            or response.css("title::text").get()
        )
        if not title:
            return

        if not publish_time:
            publish_time = self._parse_datetime(
                self._clean_text(" ".join(response.css("body ::text").getall()[:120])),
                languages=["da", "en"],
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
            author="Finanstilsynet",
            language="da",
            section="financial_regulation",
        )

    def _extract_dynamic_config(self, html_text):
        match = re.search(
            r'<div id="na_[^"]+" class="archive-search-result dynamic-list" data-config="(.*?)">',
            html_text,
        )
        if not match:
            return None
        return json.loads(html.unescape(match.group(1)))

    def _do_extract_content(self, response):
        soup = BeautifulSoup(response.text, "html.parser")
        candidates = soup.select(".rich-text")
        root = max(candidates, key=lambda node: len(node.get_text(" ", strip=True)), default=None)
        if not root:
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
            if text.startswith("Tilsyn ") or text.startswith("Ansøg og indberet "):
                continue
            if text not in parts:
                parts.append(text)
        return "\n\n".join(parts)
