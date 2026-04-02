# 菲律宾bworld爬虫，负责抓取对应站点、机构或栏目内容。

import json
import re

from bs4 import BeautifulSoup

import scrapy

from news_scraper.spiders.philippines.base import PhilippinesBaseSpider


class PhilippinesBworldSpider(PhilippinesBaseSpider):
    name = "philippines_bworld"
    allowed_domains = ["bworldonline.com", "www.bworldonline.com"]
    target_table = "phl_bworld"
    start_urls = ["https://www.bworldonline.com/economy/"]

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing)

    def parse_listing(self, response):
        html = self._fetch_html(self.start_urls[0])
        urls = sorted(
            set(
                re.findall(
                    r"https://www\.bworldonline\.com/economy/\d{4}/\d{2}/\d{2}/\d+/[a-z0-9\-]+/?",
                    html,
                )
            )
        )
        for full_url in urls:
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
        schema = self._extract_article_schema(response)
        title = self._clean_text(
            (schema or {}).get("headline")
            or response.xpath("//meta[@property='og:title']/@content").get()
            or response.css("h1::text").get()
        )
        if not title:
            return

        publish_time = self._parse_datetime(
            (schema or {}).get("datePublished")
            or response.xpath("//meta[@property='article:published_time']/@content").get()
            or response.css("time::attr(datetime), time::text").get(),
            languages=["en"],
        )
        if publish_time and not self.full_scan and publish_time < self.cutoff_date:
            return

        content = self._clean_text((schema or {}).get("articleBody")) or self._extract_content(response, title)
        if not content:
            content = self._clean_text(response.xpath("//meta[@property='og:description']/@content").get())
        if not content:
            return

        yield self._build_item(
            response=response,
            title=title,
            content=content,
            publish_time=publish_time,
            author="BusinessWorld",
            language="en",
            section="economy",
        )

    def _extract_article_schema(self, response):
        for raw in response.css('script[type="application/ld+json"]::text').getall():
            raw = raw.strip()
            if not raw:
                continue
            try:
                parsed = json.loads(raw)
            except Exception:
                continue
            candidates = parsed if isinstance(parsed, list) else [parsed]
            for candidate in candidates:
                if isinstance(candidate, dict) and candidate.get("@type") in {"NewsArticle", "Article"}:
                    return candidate
                graph = candidate.get("@graph") if isinstance(candidate, dict) else None
                if isinstance(graph, list):
                    for entry in graph:
                        if isinstance(entry, dict) and entry.get("@type") in {"NewsArticle", "Article"}:
                            return entry
        return None

    def _extract_content(self, response, title):
        soup = BeautifulSoup(response.text, "html.parser")
        root = soup.select_one("article") or soup.select_one("main") or soup.select_one(".entry-content")
        if not root:
            return ""
        for unwanted in root.select("script, style, nav, footer, header, aside, form, .sharedaddy, .related-posts"):
            unwanted.decompose()
        title_text = self._clean_text(title)
        parts = []
        for node in root.find_all(["p", "li"], recursive=True):
            text = self._clean_text(node.get_text(" ", strip=True))
            if not text or len(text) < 35 or text == title_text:
                continue
            if text.startswith("By ") or text.startswith("Reporter"):
                continue
            if text not in parts:
                parts.append(text)
        return "\n\n".join(parts)
