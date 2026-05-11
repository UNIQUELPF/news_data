# 老挝时报爬虫，抓取英文商业和经济新闻。
import json
import re

import scrapy
from scrapy_playwright.page import PageMethod

from news_scraper.spiders.laos.base import LaosBaseSpider


class LaosLaotianTimesSpider(LaosBaseSpider):
    name = "laos_laotiantimes"

    country_code = 'LAO'

    allowed_domains = ["laotiantimes.com", "www.laotiantimes.com"]
    start_urls = ["https://laotiantimes.com/category/business/"]

    # Anubis anti-bot requires a real browser; Playwright handles the
    # proof-of-work challenge (~10s on the first request). After that
    # the auth cookie persists in the shared Playwright context and
    # subsequent requests load the real page immediately.
    playwright = True
    use_curl_cffi = True

    fallback_content_selector = "article, main"

    custom_settings = {
        "DOWNLOAD_DELAY": 1.0,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
    }

    async def start(self):
        yield scrapy.Request(
            self.start_urls[0],
            callback=self.parse,
            meta={
                "playwright": True,
                "playwright_context": "laotiantimes",
                "playwright_page_methods": [
                    # Wait for the Anubis proof-of-work challenge to finish
                    PageMethod(
                        "wait_for_function",
                        "() => document.title !== \"Making sure you're not a bot!\"",
                        timeout=45000,
                    ),
                ],
            },
            dont_filter=True,
        )

    def parse(self, response):
        # --- Sanity check: if Anubis challenge was not solved, bail out ---
        if "Making sure you're not a bot!" in (response.css("title::text").get() or ""):
            self.logger.error("Anubis challenge not solved; aborting.")
            self._stop_pagination = True
            return

        links = response.css(
            'a[href*="laotiantimes.com"]::attr(href), '
            'a[href*="laotiantimes.com/2"]::attr(href)'
        ).getall()

        if not links:
            html = response.text
            links = sorted(set(re.findall(
                r"https://(?:www\.)?laotiantimes\.com/\d{4}/\d{2}/\d{2}/[a-z0-9\-]+/?",
                html
            )))

        has_valid_item_in_window = False
        seen = set()
        for url in links:
            if url in seen:
                continue
            seen.add(url)
            if not url.startswith("http"):
                continue
            if not self.should_process(url):
                continue
            has_valid_item_in_window = True
            yield scrapy.Request(
                url,
                callback=self.parse_detail,
                meta={
                    "playwright": True,
                    "playwright_context": "laotiantimes",
                },
                dont_filter=self.full_scan,
            )

        if not has_valid_item_in_window:
            self._stop_pagination = True

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
            or response.css("time::attr(datetime), time::text").get(),
            languages=["en"],
        )
        if not self.should_process(response.url, publish_time):
            self._stop_pagination = True
            return

        content = self._clean_text((schema or {}).get("articleBody")) or self._extract_content(
            response,
            ["article", "main", ".entry-content"],
        )
        if not content:
            return

        yield self._build_item(
            response=response,
            title=title,
            content=content,
            publish_time=publish_time,
            author="Laotian Times",
            language="en",
            section="business",
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
