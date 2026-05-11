# 巴林gdn爬虫，负责抓取对应站点、机构或栏目内容。

import json

from bs4 import BeautifulSoup

import scrapy

from news_scraper.spiders.bahrain.base import BahrainBaseSpider


class BahrainGdnSpider(BahrainBaseSpider):
    name = "bahrain_gdn"

    country_code = 'BHR'

    country = '巴林'
    allowed_domains = ["gdnonline.com", "www.gdnonline.com"]
    target_table = "bhr_gdn"
    start_urls = [
        "https://www.gdnonline.com/Section/4/Bahrain-Business",
    ]

    fallback_content_selector = "article, main"

    async def start(self):
        self._stop_pagination = False
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing, dont_filter=True)

    def parse_listing(self, response):
        if self._stop_pagination:
            return
        business_blocks = response.css(
            ".business-news a[href*='/Details/']::attr(href), "
            ".category-business a[href*='/Details/']::attr(href), "
            "a[href*='/Details/'][href*='Bahrain-']::attr(href)"
        ).getall()
        hrefs = business_blocks or response.css("a[href*='/Details/']::attr(href)").getall()
        has_valid_item_in_window = self.full_scan
        for href in hrefs:
            full_url = response.urljoin(href)
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
            or response.xpath("//meta[@property='og:title']/@content").get()
            or response.css("h1.entry-title::text, .penci-entry-title::text").get()
            or response.css("h1::text").get()
            or response.css("title::text").get()
        )
        if title and ":" in title:
            title = title.split(":", 1)[-1].strip()
        if not title:
            return

        publish_time = self._parse_datetime(
            (data or {}).get("datePublished")
            or response.xpath("//meta[contains(@property, 'published')]/@content").get()
            or response.xpath("//meta[contains(@name, 'publish')]/@content").get()
            or response.xpath("//meta[@property='article:published_time']/@content").get()
            or self._clean_text(response.css("time:first-of-type ::text").get())
            or self._clean_text(response.css(".entry-date.published ::text").get())
            or self._clean_text(" ".join(response.css(".entry-meta ::text, .penci-post-meta ::text").getall()))
            or self._clean_text(" ".join(response.css("body ::text").getall()[:80])),
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
            author="Gulf Daily News",
            language="en",
            section="business",
        )

    def should_process(self, url, publish_time=None):
        if self.full_scan:
            return True
        if publish_time and publish_time < self.cutoff_date:
            return False
        return url not in self.seen_urls

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
        return None

    def _extract_content(self, response, title):
        soup = BeautifulSoup(response.text, "html.parser")
        root = (
            soup.select_one(".penci-entry-content.entry-content")
            or soup.select_one(".entry-content")
            or soup.select_one(".penci-single-artcontent")
            or soup.select_one("article")
            or soup.select_one("main")
            or soup.select_one(".article-body")
            or soup.select_one(".story")
        )
        if not root:
            return ""

        for unwanted in root.select("script, style, nav, footer, header, aside, form, .advertisement, .related"):
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
