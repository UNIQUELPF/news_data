import json
import re
from datetime import datetime
from urllib.parse import urlparse

import scrapy
from bs4 import BeautifulSoup

from news_scraper.spiders.smart_spider import SmartSpider


class USABusinessMediaSpider(SmartSpider):
    source_timezone = "America/New_York"
    country_code = "USA"
    country = "美国"
    language = "en"
    strict_date_required = False
    use_curl_cffi = True
    dateparser_settings = {"DATE_ORDER": "MDY"}

    start_urls = []
    section_name = "Business"
    organization = None
    include_url_patterns = ()
    exclude_url_patterns = (
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".webp",
        ".svg",
        ".pdf",
        "/video/",
        "/videos/",
        "/podcast",
        "/podcasts/",
        "/sponsored/",
        "/advertising/",
        "/privacy",
        "/terms",
        "/login",
        "/subscribe",
        "/account",
        "#",
    )
    article_link_selectors = (
        "article a::attr(href)",
        "h1 a::attr(href)",
        "h2 a::attr(href)",
        "h3 a::attr(href)",
        "a[href*='/20']::attr(href)",
        "a[href*='/news/']::attr(href)",
        "a[href*='/article/']::attr(href)",
        "a[href*='/story/']::attr(href)",
    )

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_DELAY": 1.0,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 3,
        "DEFAULT_REQUEST_HEADERS": {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
        },
    }

    async def start(self):
        for url in self.start_urls:
            yield scrapy.Request(
                url,
                callback=self.parse,
                meta={"section_hint": self.section_name},
                dont_filter=True,
            )

    def parse(self, response):
        seen = set()
        has_valid_item_in_window = False

        for href in self._extract_links(response):
            url = response.urljoin(href).split("#")[0]
            if url in seen or not self._is_article_url(url):
                continue
            seen.add(url)

            publish_time = self._date_from_url(url)
            if publish_time and not self.should_process(url, publish_time):
                continue
            if not publish_time and self.is_already_scraped(url):
                continue

            has_valid_item_in_window = True
            meta = {"section_hint": response.meta.get("section_hint", self.section_name)}
            if publish_time:
                meta["publish_time_hint"] = publish_time
            yield scrapy.Request(url, callback=self.parse_detail, meta=meta)

        if has_valid_item_in_window:
            next_url = response.css(
                "a[rel='next']::attr(href), a.next::attr(href), a.pagination-next::attr(href)"
            ).get()
            if next_url:
                yield response.follow(
                    next_url,
                    callback=self.parse,
                    meta={"section_hint": response.meta.get("section_hint", self.section_name)},
                )

    def parse_detail(self, response):
        item = self.auto_parse_item(response)
        if not item.get("publish_time"):
            item["publish_time"] = self._extract_jsonld_date(response) or self._date_from_url(response.url)
        if not item.get("publish_time"):
            return
        if not self.should_process(response.url, item.get("publish_time")):
            return

        fallback_text = self._fallback_content(response)
        if len(fallback_text) > len(item.get("content_plain") or ""):
            item["content_plain"] = fallback_text
            item.setdefault("content_cleaned", fallback_text)
            item.setdefault("content_markdown", fallback_text)

        if not item.get("content_plain") or len(item["content_plain"]) < 120:
            return
        if not self.is_valid_article_item(item):
            return

        item["author"] = item.get("author") or self._extract_author(response) or self.organization or self.name
        item["section"] = response.meta.get("section_hint", self.section_name)
        item["organization"] = self.organization
        yield item

    def _extract_links(self, response):
        links = []
        for selector in self.article_link_selectors:
            links.extend(response.css(selector).getall())
        for data in response.xpath("//script[@type='application/ld+json']/text()").getall():
            try:
                self._collect_urls(json.loads(data), links)
            except Exception:
                continue
        return links

    def _is_article_url(self, url):
        parsed = urlparse(url)
        if not parsed.scheme.startswith("http"):
            return False
        if self.allowed_domains and not any(parsed.netloc.endswith(domain) for domain in self.allowed_domains):
            return False
        if any(pattern in url for pattern in self.exclude_url_patterns):
            return False
        if self.include_url_patterns and not any(pattern in url for pattern in self.include_url_patterns):
            return False
        if not self.should_follow_article_url(url):
            return False
        return True

    def _date_from_url(self, url):
        patterns = (
            r"/(\d{4})/(\d{1,2})/(\d{1,2})/",
            r"[-_/](\d{4})[-_/](\d{1,2})[-_/](\d{1,2})(?:[-_/]|$)",
        )
        for pattern in patterns:
            match = re.search(pattern, url)
            if not match:
                continue
            try:
                return self.parse_to_utc(
                    datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)))
                )
            except ValueError:
                continue
        return None

    def _extract_jsonld_date(self, response):
        for data in response.xpath("//script[@type='application/ld+json']/text()").getall():
            try:
                parsed = json.loads(data)
            except Exception:
                continue
            date_text = self._deep_find(parsed, ("datePublished", "dateCreated", "uploadDate"))
            if date_text:
                return self.parse_date(date_text)
        return None

    def _extract_author(self, response):
        return (
            response.xpath("//meta[@name='author']/@content").get()
            or response.xpath("//meta[@property='article:author']/@content").get()
            or response.css("[rel='author']::text, .author::text, .byline::text").get()
        )

    def _fallback_content(self, response):
        selectors = [
            getattr(self, "fallback_content_selector", None),
            "article",
            "main",
            "[itemprop='articleBody']",
            ".article-body",
            ".story-body",
            ".entry-content",
        ]
        for selector in selectors:
            if not selector:
                continue
            html = response.css(selector).get()
            if not html:
                continue
            soup = BeautifulSoup(html, "html.parser")
            for tag in soup(["script", "style", "aside", "nav", "footer", "form", "button"]):
                tag.decompose()
            parts = []
            for node in soup.find_all(["p", "h2", "h3", "li"]):
                text = node.get_text(" ", strip=True)
                if len(text) > 35:
                    parts.append(text)
            text = "\n\n".join(dict.fromkeys(parts))
            if len(text) >= 120:
                return text
        return ""

    @classmethod
    def _collect_urls(cls, obj, out):
        if isinstance(obj, dict):
            for key in ("url", "mainEntityOfPage"):
                value = obj.get(key)
                if isinstance(value, str):
                    out.append(value)
                elif isinstance(value, dict) and isinstance(value.get("@id"), str):
                    out.append(value["@id"])
            for value in obj.values():
                cls._collect_urls(value, out)
        elif isinstance(obj, list):
            for value in obj:
                cls._collect_urls(value, out)

    @classmethod
    def _deep_find(cls, obj, keys):
        if isinstance(obj, dict):
            for key in keys:
                value = obj.get(key)
                if value:
                    return value
            for value in obj.values():
                found = cls._deep_find(value, keys)
                if found:
                    return found
        elif isinstance(obj, list):
            for value in obj:
                found = cls._deep_find(value, keys)
                if found:
                    return found
        return None
