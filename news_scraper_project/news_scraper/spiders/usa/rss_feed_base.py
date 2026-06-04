import html
import re
import xml.etree.ElementTree as ET

import scrapy
import requests
from bs4 import BeautifulSoup

from news_scraper.spiders.smart_spider import SmartSpider


class USARssFeedSpider(SmartSpider):
    source_timezone = "America/New_York"
    country_code = "USA"
    country = "美国"
    language = "en"
    strict_date_required = True
    use_curl_cffi = False
    dateparser_settings = {"DATE_ORDER": "MDY"}
    section_name = "News"
    organization = None
    feed_urls = []
    start_date = "2026-01-01"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_DELAY": 0.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_HANDLERS": {
            "http": "scrapy.core.downloader.handlers.http11.HTTP11DownloadHandler",
            "https": "scrapy.core.downloader.handlers.http11.HTTP11DownloadHandler",
        },
        "DEFAULT_REQUEST_HEADERS": {
            "Accept": "application/rss+xml,application/xml,text/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        },
    }

    async def start(self):
        for url in self.feed_urls:
            for item in self._request_feed(url):
                yield item

    def _request_feed(self, url):
        try:
            response = requests.get(
                url,
                headers=self.custom_settings["DEFAULT_REQUEST_HEADERS"],
                timeout=30,
                verify=False,
            )
            response.raise_for_status()
        except Exception as exc:
            self.logger.error(f"RSS request failed for {url}: {exc}")
            return []
        return list(self._parse_feed_text(response.text, url))

    def parse_feed(self, response):
        yield from self._parse_feed_text(response.text, response.url)

    def _parse_feed_text(self, text, feed_url):
        try:
            root = ET.fromstring(text.encode("utf-8"))
        except Exception as exc:
            self.logger.error(f"RSS parse failed for {feed_url}: {exc}")
            return

        for entry in root.findall(".//item") + root.findall(".//{http://www.w3.org/2005/Atom}entry"):
            title = self._entry_text(entry, "title")
            link = self._entry_link(entry)
            date_text = (
                self._entry_text(entry, "pubDate")
                or self._entry_text(entry, "published")
                or self._entry_text(entry, "updated")
                or self._entry_text(entry, "{http://purl.org/dc/elements/1.1/}date")
            )
            publish_time = self.parse_date(date_text)
            if not link or not title or not publish_time:
                continue
            if not self.should_process(link, publish_time):
                continue

            content_html = (
                self._entry_text(entry, "{http://purl.org/rss/1.0/modules/content/}encoded")
                or self._entry_text(entry, "description")
                or self._entry_text(entry, "summary")
            )
            content_plain = self._clean_html(content_html)
            if len(content_plain) < 40:
                content_plain = title

            yield {
                "url": link,
                "title": html.unescape(title).strip(),
                "raw_html": content_html or "",
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

    def _clean_html(self, value):
        if not value:
            return ""
        value = html.unescape(value)
        soup = BeautifulSoup(value, "html.parser")
        for tag in soup(["script", "style"]):
            tag.decompose()
        text = soup.get_text(" ", strip=True)
        return re.sub(r"\s+", " ", text).strip()
