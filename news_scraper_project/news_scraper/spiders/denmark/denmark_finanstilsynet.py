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
    target_table = "dnk_finanstilsynet"
    start_urls = ["https://www.finanstilsynet.dk/nyheder-og-presse/nyheder-og-pressemeddelelser"]

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing)

    def parse_listing(self, response):
        html_text = self._fetch_html(self.start_urls[0])
        config = self._extract_dynamic_config(html_text)
        if not config:
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
        except Exception:
            return

        page_html = result.get("pageHtml", "")
        soup = BeautifulSoup(page_html, "html.parser")
        for card in soup.select(".item"):
            link = card.select_one("a[href]")
            if not link:
                continue
            full_url = link.get("href")
            if not full_url or full_url in self.seen_urls:
                continue
            publish_time = None
            date_node = card.select_one("[data-date]")
            if date_node:
                publish_time = self._parse_datetime(date_node.get("data-date"), languages=["da", "en"])
            if publish_time and not self.full_scan and publish_time < self.cutoff_date:
                continue
            self.seen_urls.add(full_url)
            try:
                detail_html = self._fetch_html(full_url)
            except Exception:
                continue
            item = next(self.parse_detail(self._make_response(full_url, detail_html), publish_time=publish_time), None)
            if item:
                yield item

    def parse_detail(self, response, publish_time=None):
        title = self._clean_text(
            response.xpath("//meta[@property='og:title']/@content").get()
            or response.css("h1::text").get()
            or response.css("title::text").get()
        )
        if not title:
            return

        final_publish_time = publish_time or self._parse_datetime(
            self._clean_text(" ".join(response.css("body ::text").getall()[:120])),
            languages=["da", "en"],
        )
        if final_publish_time and not self.full_scan and final_publish_time < self.cutoff_date:
            return

        content = self._extract_content(response)
        if not content:
            return

        yield self._build_item(
            response=response,
            title=title,
            content=content,
            publish_time=final_publish_time,
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

    def _extract_content(self, response):
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
