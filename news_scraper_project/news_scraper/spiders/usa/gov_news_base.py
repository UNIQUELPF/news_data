import json
import re
from datetime import datetime
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from news_scraper.spiders.smart_spider import SmartSpider


class USAGovNewsSpider(SmartSpider):
    source_timezone = "America/New_York"
    country_code = "USA"
    country = "美国"
    language = "en"
    strict_date_required = True
    use_curl_cffi = False
    dateparser_settings = {"DATE_ORDER": "MDY"}
    start_date = "2026-01-01"

    list_urls = []
    include_url_patterns = ()
    exclude_url_patterns = (
        ".pdf",
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".webp",
        ".svg",
        "#",
        "/events/",
        "/speeches/",
        "/testimony/",
    )
    fallback_content_selector = "main, article, .content, .region-content, .field--name-body"
    section_name = "News"
    organization = None
    max_pages = 3
    max_items = 25

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_DELAY": 0.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
    }

    async def start(self):
        for item in self._crawl_lists():
            yield item

    def _crawl_lists(self):
        queued = set()
        yielded = 0
        for list_url in self.list_urls:
            for page_url in self._iter_list_pages(list_url):
                html = self._fetch(page_url)
                if not html:
                    continue
                soup = BeautifulSoup(html, "html.parser")
                for link, title_hint, date_hint in self._extract_listing_links(soup, page_url):
                    if link in queued:
                        continue
                    queued.add(link)
                    detail_html = self._fetch(link)
                    if not detail_html:
                        continue
                    item = self._build_item(link, detail_html, title_hint, date_hint)
                    if item:
                        yielded += 1
                        yield item
                        if yielded >= self.max_items:
                            return

    def _iter_list_pages(self, list_url):
        current = list_url
        seen = set()
        for _ in range(self.max_pages):
            if not current or current in seen:
                return
            seen.add(current)
            yield current
            html = self._fetch(current)
            if not html:
                return
            soup = BeautifulSoup(html, "html.parser")
            next_href = self._find_next_url(soup)
            current = requests.compat.urljoin(current, next_href) if next_href else None

    def _fetch(self, url):
        try:
            response = requests.get(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                    "Accept-Language": "en-US,en;q=0.9",
                },
                timeout=30,
                verify=False,
            )
            if response.status_code >= 400:
                self.logger.warning(f"Fetch returned {response.status_code}: {url}")
                return None
            return response.text
        except Exception as exc:
            self.logger.error(f"Fetch failed for {url}: {exc}")
            return None

    def _extract_listing_links(self, soup, base_url):
        for loc in soup.find_all("loc"):
            link = loc.get_text(strip=True)
            if not self._is_article_url(link):
                continue
            parent = loc.parent
            lastmod = parent.find("lastmod") if parent else None
            date_hint = self.parse_date(lastmod.get_text(strip=True)) if lastmod else None
            yield link, "", date_hint or self._parse_date_from_url(link)

        selectors = (
            "article a[href], h2 a[href], h3 a[href], .views-row a[href], "
            ".field--item a[href], .field-content a[href], .usa-collection a[href], "
            ".card a[href], a[href]"
        )
        for a in soup.select(selectors):
            href = a.get("href")
            if not href:
                continue
            link = requests.compat.urljoin(base_url, href).split("#")[0]
            if not self._is_article_url(link):
                continue
            title = a.get_text(" ", strip=True)
            container = a
            for _ in range(5):
                if container.parent:
                    container = container.parent
            context = container.get_text(" ", strip=True)
            yield link, title, self._parse_date_from_text(context) or self._parse_date_from_url(link)

    def _is_article_url(self, url):
        parsed = urlparse(url)
        if self.allowed_domains and not any(parsed.netloc.endswith(domain) for domain in self.allowed_domains):
            return False
        if any(pattern in url for pattern in self.exclude_url_patterns):
            return False
        if self.include_url_patterns and not any(pattern in url for pattern in self.include_url_patterns):
            return False
        if not self.should_follow_article_url(url):
            return False
        return True

    def _build_item(self, url, raw_html, title_hint=None, date_hint=None):
        soup = BeautifulSoup(raw_html, "html.parser")
        title = (
            title_hint
            or self._meta(soup, "property", "og:title")
            or self._meta(soup, "name", "twitter:title")
            or self._first_text(soup, "h1")
        )
        detail_time = self._extract_detail_date(soup, url)
        earliest_date = getattr(self, "earliest_date", None)
        if date_hint and detail_time and earliest_date and detail_time < earliest_date <= date_hint:
            publish_time = date_hint
        else:
            publish_time = detail_time or date_hint
        if not title or not publish_time:
            return None
        if not self.should_process(url, publish_time):
            return None
        content_plain = self._extract_content(soup)
        if len(content_plain) < 120:
            return None
        item = {
            "url": url,
            "title": title.strip(),
            "raw_html": raw_html,
            "content_cleaned": content_plain,
            "content_markdown": content_plain,
            "content_plain": content_plain,
            "images": [],
            "publish_time": publish_time,
            "author": self.organization or self.name,
            "language": self.language,
            "section": self.section_name,
            "category": self.section_name,
            "country_code": self.country_code,
            "country": self.country,
            "organization": self.organization,
        }
        return item if self.is_valid_article_item(item) else None

    def _extract_detail_date(self, soup, url):
        for attr, key in (
            ("property", "article:published_time"),
            ("name", "date"),
            ("name", "publishdate"),
            ("name", "DC.date"),
            ("name", "dcterms.date"),
        ):
            value = self._meta(soup, attr, key)
            if value:
                parsed = self.parse_date(value)
                if parsed:
                    return parsed
        time_node = soup.select_one("time[datetime]")
        if time_node:
            parsed = self.parse_date(time_node.get("datetime"))
            if parsed:
                return parsed
        for script in soup.select("script[type='application/ld+json']"):
            try:
                value = self._deep_find(json.loads(script.get_text(strip=True)), ("datePublished", "dateCreated", "uploadDate"))
            except Exception:
                value = None
            if value:
                parsed = self.parse_date(value)
                if parsed:
                    return parsed
        text = soup.get_text(" ", strip=True)[:2500]
        return self._parse_date_from_text(text) or self._parse_date_from_url(url)

    def _parse_date_from_text(self, text):
        if not text:
            return None
        patterns = (
            r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}\b",
            r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\s+\d{1,2},?\s+\d{4}\b",
            r"\b\d{1,2}/\d{1,2}/\d{4}\b",
            r"\b\d{4}-\d{2}-\d{2}\b",
        )
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                parsed = self.parse_date(match.group(0))
                if parsed:
                    return parsed
        return None

    def _parse_date_from_url(self, url):
        match = re.search(r"/(\d{4})/(\d{1,2})/(\d{1,2})/", url) or re.search(r"-(\d{4})-(\d{2})-(\d{2})(?:/|$)", url)
        if not match:
            return None
        try:
            return self.parse_to_utc(datetime(int(match.group(1)), int(match.group(2)), int(match.group(3))))
        except ValueError:
            return None

    def _extract_content(self, soup):
        selector = getattr(self, "fallback_content_selector", None) or "main, article"
        body = soup.select_one(selector) or soup.select_one("main") or soup.select_one("article") or soup.body
        if not body:
            return ""
        body = BeautifulSoup(str(body), "html.parser")
        for tag in body(["script", "style", "nav", "footer", "header", "form", "button", "aside"]):
            tag.decompose()
        parts = []
        for node in body.find_all(["p", "h2", "h3", "li"]):
            text = node.get_text(" ", strip=True)
            if len(text) > 35:
                parts.append(text)
        return "\n\n".join(dict.fromkeys(parts))

    def _find_next_url(self, soup):
        node = soup.select_one("a[rel='next'], a.next, .pager__item--next a, .pagination-next a, a[aria-label*='Next']")
        if node:
            return node.get("href")
        for a in soup.select("a[href]"):
            if a.get_text(" ", strip=True).lower() in {"next", "next page", ">", "›"}:
                return a.get("href")
        return None

    @staticmethod
    def _meta(soup, attr, key):
        node = soup.find("meta", attrs={attr: key})
        return node.get("content", "").strip() if node and node.get("content") else None

    @staticmethod
    def _first_text(soup, selector):
        node = soup.select_one(selector)
        return node.get_text(" ", strip=True) if node else None

    @classmethod
    def _deep_find(cls, obj, keys):
        if isinstance(obj, dict):
            for key in keys:
                if obj.get(key):
                    return obj[key]
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
