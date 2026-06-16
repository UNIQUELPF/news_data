import html
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from news_scraper.spiders.smart_spider import SmartSpider


class GermanyNewsBaseSpider(SmartSpider):
    country_code = "DEU"
    country = "德国"
    language = "de"
    source_timezone = "Europe/Berlin"
    strict_date_required = True
    use_curl_cffi = False
    dateparser_settings = {"DATE_ORDER": "DMY"}
    start_date = "2026-01-01"

    source_name = None
    organization = None
    subscription_required = False
    access_note = "无需订阅"
    section_name = "News"
    list_urls = []
    feed_urls = []
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
        "/login",
        "/newsletter",
        "/impressum",
        "/datenschutz",
    )
    fallback_content_selector = (
        "main article, article, main, .article, .content, .richtext, "
        ".c-detail, .c-article, .pressrelease, .text"
    )
    max_pages = 2
    max_items = 5
    fetch_detail_pages = True
    prefer_list_urls = False
    request_timeout = 6
    max_list_candidates = 25

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_DELAY": 0.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_HANDLERS": {
            "http": "scrapy.core.downloader.handlers.http11.HTTP11DownloadHandler",
            "https": "scrapy.core.downloader.handlers.http11.HTTP11DownloadHandler",
        },
        "DEFAULT_REQUEST_HEADERS": {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        },
    }

    async def start(self):
        yielded = 0
        sources = (
            (self._crawl_lists(), self.feed_urls)
            if self.prefer_list_urls
            else (None, self.feed_urls)
        )
        if sources[0] is not None:
            for item in sources[0]:
                yielded += 1
                yield item
                if yielded >= self.max_items:
                    return
        for feed_url in sources[1]:
            for item in self._crawl_feed(feed_url):
                yielded += 1
                yield item
                if yielded >= self.max_items:
                    return
        if not self.prefer_list_urls:
            for item in self._crawl_lists():
                yielded += 1
                yield item
                if yielded >= self.max_items:
                    return

    def _crawl_feed(self, feed_url):
        text = self._fetch_text(feed_url)
        if not text:
            return
        try:
            root = ET.fromstring(text.encode("utf-8"))
        except Exception as exc:
            self.logger.warning(f"Feed parse failed for {feed_url}: {exc}")
            return
        entries = root.findall(".//item") + root.findall(".//{http://www.w3.org/2005/Atom}entry")
        for entry in entries:
            title = self._entry_text(entry, "title")
            link = self._entry_link(entry)
            publish_time = self.parse_date(
                self._entry_text(entry, "pubDate")
                or self._entry_text(entry, "published")
                or self._entry_text(entry, "updated")
                or self._entry_text(entry, "{http://purl.org/dc/elements/1.1/}date")
            )
            if not title or not link or not publish_time or not self.should_process(link, publish_time):
                continue
            content_html = (
                self._entry_text(entry, "{http://purl.org/rss/1.0/modules/content/}encoded")
                or self._entry_text(entry, "description")
                or self._entry_text(entry, "summary")
                or ""
            )
            raw_html = content_html
            content_plain = self._html_to_text(content_html)
            detail_link = self._normalize_feed_link(link)
            if self.fetch_detail_pages and self._is_allowed_domain(detail_link):
                detail_html = self._fetch_text(detail_link)
                if detail_html:
                    detail_plain = self._extract_content_text(detail_html)
                    if len(detail_plain) >= 120:
                        raw_html = detail_html
                        content_plain = detail_plain
                        link = detail_link
            if len(content_plain) < 40:
                content_plain = html.unescape(title)
            item = self._make_item(link, title, raw_html, content_plain, publish_time)
            if item:
                yield item

    def _crawl_lists(self):
        queued = set()
        for list_url in self.list_urls:
            current = list_url
            for _ in range(self.max_pages):
                if not current:
                    break
                page_html = self._fetch_text(current)
                if not page_html:
                    break
                if page_html.lstrip().startswith(("{", "[")):
                    for link, title_hint, date_hint in self._extract_json_listing_links(page_html, current):
                        if link in queued:
                            continue
                        queued.add(link)
                        detail_html = self._fetch_text(link)
                        if not detail_html:
                            continue
                        item = self._build_detail_item(link, detail_html, title_hint, date_hint)
                        if item:
                            yield item
                    break
                soup = BeautifulSoup(page_html, "html.parser")
                base_node = soup.select_one("base[href]")
                page_base = urljoin(current, base_node.get("href")) if base_node else current
                candidate_count = 0
                for link, title_hint, date_hint in self._extract_listing_links(soup, page_base):
                    if link in queued:
                        continue
                    queued.add(link)
                    candidate_count += 1
                    if candidate_count > self.max_list_candidates:
                        break
                    detail_html = self._fetch_text(link)
                    if not detail_html:
                        continue
                    item = self._build_detail_item(link, detail_html, title_hint, date_hint)
                    if item:
                        yield item
                next_href = self._find_next_url(soup)
                current = urljoin(current, next_href) if next_href else None

    def _build_detail_item(self, url, raw_html, title_hint=None, date_hint=None):
        soup = BeautifulSoup(raw_html, "html.parser")
        title = (
            title_hint
            or self._meta(soup, "property", "og:title")
            or self._meta(soup, "name", "twitter:title")
            or self._first_text(soup, "h1")
            or self._first_text(soup, "title")
        )
        publish_time = self._extract_detail_date(soup, url) or date_hint
        if not title or not publish_time or not self.should_process(url, publish_time):
            return None
        content_plain = self._extract_content_text(raw_html)
        if len(content_plain) < 120:
            return None
        return self._make_item(url, title, raw_html, content_plain, publish_time)

    def _make_item(self, url, title, raw_html, content_plain, publish_time):
        content_plain = self._clean_text(content_plain)
        item = {
            "url": url,
            "title": html.unescape(self._clean_text(title)),
            "raw_html": raw_html or "",
            "content_cleaned": content_plain,
            "content_markdown": content_plain,
            "content_plain": content_plain,
            "images": [],
            "publish_time": publish_time,
            "author": self.organization or self.source_name or self.name,
            "language": self.language,
            "section": self.section_name,
            "category": self.section_name,
            "country_code": self.country_code,
            "country": self.country,
            "organization": self.organization,
            "subscription_required": self.subscription_required,
            "access_note": self.access_note,
        }
        return item if self.is_valid_article_item(item) else None

    def _fetch_text(self, url):
        try:
            response = requests.get(
                url,
                headers=self.custom_settings["DEFAULT_REQUEST_HEADERS"],
                timeout=self.request_timeout,
                verify=False,
                allow_redirects=True,
            )
            if response.status_code >= 400:
                self.logger.warning(f"Fetch returned {response.status_code}: {url}")
                return None
            return response.text
        except Exception as exc:
            self.logger.warning(f"Fetch failed for {url}: {exc}")
            return None

    def _normalize_feed_link(self, link):
        return link

    def _extract_listing_links(self, soup, base_url):
        for link in self._extract_urls_from_markup(str(soup), base_url):
            if self._is_article_url(link):
                yield link, "", self._parse_date_from_url(link)

        selectors = (
            "article a[href], h2 a[href], h3 a[href], .teaser a[href], "
            ".c-result a[href], .searchresult a[href], .result-list a[href], "
            ".item a[href], .card a[href], .news-list a[href], a[href]"
        )
        for a in soup.select(selectors):
            href = a.get("href")
            if not href:
                continue
            link = urljoin(base_url, href).split("#")[0]
            if not self._is_article_url(link):
                continue
            container = a
            for _ in range(5):
                if container.parent:
                    container = container.parent
            context = container.get_text(" ", strip=True)
            yield link, a.get_text(" ", strip=True), self._parse_date_from_text(context) or self._parse_date_from_url(link)

    def _extract_json_listing_links(self, text, base_url):
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return
        items = data if isinstance(data, list) else data.get("items", [])
        for entry in items:
            if not isinstance(entry, dict):
                continue
            href = entry.get("link") or entry.get("url") or entry.get("href")
            if not href:
                continue
            link = urljoin(base_url, href).split("#")[0]
            if not self._is_article_url(link):
                continue
            title = entry.get("teaserHeadline") or entry.get("title") or entry.get("headline") or ""
            date_hint = self.parse_date(entry.get("pubDate") or entry.get("date") or entry.get("published"))
            yield link, title, date_hint or self._parse_date_from_url(link)

    def _extract_urls_from_markup(self, markup, base_url):
        seen = set()
        patterns = (
            r"https?://[^\"'<>\\\s]+",
            r"(?<![A-Za-z0-9])/(?:[A-Za-z0-9._~:/?#\[\]@!$&()*+,;=%-]+)",
        )
        for pattern in patterns:
            for match in re.finditer(pattern, markup or ""):
                url = html.unescape(match.group(0)).rstrip("\\),.;")
                try:
                    link = urljoin(base_url, url).split("#")[0]
                except ValueError:
                    continue
                if link in seen:
                    continue
                seen.add(link)
                yield link

    def _is_article_url(self, url):
        if not self._is_allowed_domain(url):
            return False
        if self._is_list_url(url):
            return False
        if any(pattern in url for pattern in self.exclude_url_patterns):
            return False
        if self.include_url_patterns and not any(pattern in url for pattern in self.include_url_patterns):
            return False
        return True

    def _is_list_url(self, url):
        try:
            parsed_url = urlparse(url)
        except ValueError:
            return True
        normalized = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}".rstrip("/")
        for list_url in self.list_urls:
            try:
                parsed_list = urlparse(list_url)
            except ValueError:
                continue
            normalized_list = f"{parsed_list.scheme}://{parsed_list.netloc}{parsed_list.path}".rstrip("/")
            if normalized == normalized_list:
                return True
        return False

    def _is_allowed_domain(self, url):
        try:
            parsed = urlparse(url)
        except ValueError:
            return False
        return not self.allowed_domains or any(parsed.netloc.endswith(domain) for domain in self.allowed_domains)

    def _extract_detail_date(self, soup, url):
        for attr, key in (
            ("property", "article:published_time"),
            ("property", "og:published_time"),
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
        return self._parse_date_from_text(soup.get_text(" ", strip=True)[:3000]) or self._parse_date_from_url(url)

    def _parse_date_from_text(self, text):
        if not text:
            return None
        patterns = (
            r"\b\d{1,2}\.\s*(?:Januar|Februar|März|Maerz|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)\s+\d{4}\b",
            r"\b\d{1,2}\.\d{1,2}\.\d{4}\b",
            r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}\b",
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
        match = re.search(r"/(20\d{2})/(\d{1,2})/", url) or re.search(r"-(20\d{2})(\d{2})(\d{2})(?:\\D|$)", url)
        if match:
            try:
                if len(match.groups()) == 2:
                    return self.parse_to_utc(datetime(int(match.group(1)), int(match.group(2)), 1))
                return self.parse_to_utc(datetime(int(match.group(1)), int(match.group(2)), int(match.group(3))))
            except ValueError:
                return None
        match = re.search(r"/(\d{1,2})_(\d{1,2})_(20\d{2})(?:\D|$)", url)
        if not match:
            return None
        try:
            return self.parse_to_utc(datetime(int(match.group(3)), int(match.group(1)), int(match.group(2))))
        except ValueError:
            return None

    def _extract_content_text(self, raw_html):
        soup = BeautifulSoup(raw_html or "", "html.parser")
        root = soup.select_one(getattr(self, "fallback_content_selector", None) or "main, article") or soup.body
        if not root:
            return ""
        root = BeautifulSoup(str(root), "html.parser")
        for tag in root.select("script, style, nav, footer, header, aside, form, button, .breadcrumb, .share, .social"):
            tag.decompose()
        parts = []
        for node in root.find_all(["p", "li", "h2", "h3"], recursive=True):
            text = self._clean_text(node.get_text(" ", strip=True))
            if len(text) >= 35 and text not in parts:
                parts.append(text)
        return "\n\n".join(parts)

    def _find_next_url(self, soup):
        node = soup.select_one("a[rel='next'], a.next, .pagination .next a, .c-pagination__next a")
        if node:
            return node.get("href")
        for a in soup.select("a[href]"):
            if a.get_text(" ", strip=True).lower() in {"next", "weiter", "nächste", ">" , "›"}:
                return a.get("href")
        return None

    def _entry_text(self, entry, tag):
        node = entry.find(tag)
        if node is None:
            node = entry.find(f"{{http://www.w3.org/2005/Atom}}{tag}")
        return node.text.strip() if node is not None and node.text else None

    def _entry_link(self, entry):
        link = self._entry_text(entry, "link")
        if link:
            return link.strip()
        atom_link = entry.find("{http://www.w3.org/2005/Atom}link")
        if atom_link is not None:
            return (atom_link.attrib.get("href") or "").strip()
        return None

    def _html_to_text(self, value):
        if not value:
            return ""
        soup = BeautifulSoup(html.unescape(value), "html.parser")
        for tag in soup.select("script, style"):
            tag.decompose()
        return self._clean_text(soup.get_text(" ", strip=True))

    def _clean_text(self, value):
        return re.sub(r"\s+", " ", str(value or "").replace("\x00", " ")).strip()

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
        if isinstance(obj, list):
            for value in obj:
                found = cls._deep_find(value, keys)
                if found:
                    return found
        return None
