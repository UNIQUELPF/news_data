# 巴基斯坦dawn爬虫，负责抓取对应站点、机构或栏目内容。

import json

from bs4 import BeautifulSoup

import scrapy

from news_scraper.spiders.pakistan.base import PakistanBaseSpider


class PakistanDawnSpider(PakistanBaseSpider):
    name = "pakistan_dawn"

    country_code = 'PAK'

    country = '巴基斯坦'
    allowed_domains = ["dawn.com", "www.dawn.com"]
    target_table = "pak_dawn"

    use_curl_cffi = True
    fallback_content_selector = "article, main"

    start_urls = [
        "https://www.dawn.com/business",
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._stop_pagination = False

    def should_process(self, url, publish_time=None):
        if self.full_scan:
            return True
        if publish_time and publish_time < self.cutoff_date:
            return False
        return url not in self.seen_urls

    async def start(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing, dont_filter=True)

    def parse_listing(self, response):
        if self._stop_pagination:
            return

        has_valid_item_in_window = self.full_scan

        for href in response.css("a::attr(href)").getall():
            if self._stop_pagination:
                break
            full_url = response.urljoin(href)
            if "/news/" not in full_url:
                continue
            # Use should_process instead of raw seen_urls check for full_scan support
            if not self.should_process(full_url):
                continue
            self.seen_urls.add(full_url)
            has_valid_item_in_window = True
            yield scrapy.Request(full_url, callback=self.parse_detail, dont_filter=self.full_scan)

        if not has_valid_item_in_window:
            self._stop_pagination = True

    def parse_detail(self, response):
        data = self._extract_article_schema(response)
        title = self._clean_text(
            (data or {}).get("headline")
            or (data or {}).get("name")
            or response.xpath("//meta[@property='og:title']/@content").get()
            or response.css("h1::text").get()
        )
        if not title:
            return

        publish_time = self._parse_datetime(
            (data or {}).get("datePublished")
            or response.xpath("//meta[@property='article:published_time']/@content").get()
            or response.css("time::attr(datetime), time::text").get(),
            languages=["en"],
        )
        if not self.should_process(response.url, publish_time):
            self._stop_pagination = True
            return

        content = self._clean_text((data or {}).get("articleBody")) or self._extract_content(response, title)
        if not content:
            content = self._clean_text(response.xpath("//meta[@name='description']/@content").get())
        if not content:
            return

        yield self._build_item(
            response=response,
            title=title,
            content=content,
            publish_time=publish_time,
            author="Dawn",
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
                if not isinstance(graph, list):
                    continue
                for entry in graph:
                    if isinstance(entry, dict) and entry.get("@type") in {"NewsArticle", "Article"}:
                        return entry
        return None

    def _extract_content(self, response, title):
        soup = BeautifulSoup(response.text, "html.parser")
        root = soup.select_one("article") or soup.select_one("main")
        if not root:
            return ""

        for unwanted in root.select("script, style, nav, footer, header, aside, form, .story__sidebar, .advertisement"):
            unwanted.decompose()

        title_text = self._clean_text(title)
        parts = []
        for node in root.find_all(["p", "h2", "h3", "li"], recursive=True):
            text = self._clean_text(node.get_text(" ", strip=True))
            if not text or len(text) < 30 or text == title_text:
                continue
            if text not in parts:
                parts.append(text)
        return "\n\n".join(parts)
