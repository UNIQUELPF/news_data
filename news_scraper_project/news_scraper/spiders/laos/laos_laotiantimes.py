# 老挝时报爬虫，抓取英文商业和经济新闻。
import json
import re

import scrapy

from news_scraper.spiders.laos.base import LaosBaseSpider


class LaosLaotianTimesSpider(LaosBaseSpider):
    name = "laos_laotiantimes"

    country_code = 'LAO'

    country = '老挝'
    allowed_domains = ["laotiantimes.com", "www.laotiantimes.com"]
    target_table = "lao_laotiantimes"
    start_urls = ["https://laotiantimes.com/category/business/"]

    def parse(self, response):
        html = self._fetch_html(self.start_urls[0])
        urls = sorted(set(re.findall(r"https://laotiantimes\.com/\d{4}/\d{2}/\d{2}/[a-z0-9\-]+/?", html)))
        for url in urls[:15]:
            if url in self.seen_urls:
                continue
            self.seen_urls.add(url)
            yield scrapy.Request(url, callback=self.parse_detail)

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
        if publish_time and not self.full_scan and publish_time < self.cutoff_date:
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
