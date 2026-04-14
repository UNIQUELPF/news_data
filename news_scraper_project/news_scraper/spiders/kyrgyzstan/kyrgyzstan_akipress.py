# 吉尔吉斯斯坦 AKIpress 英文经济新闻爬虫，抓取 economy 和 finance 栏目。

import re
from urllib.parse import urljoin

import scrapy
from bs4 import BeautifulSoup

from news_scraper.spiders.kyrgyzstan.base import KyrgyzstanBaseSpider


class KyrgyzstanAkipressSpider(KyrgyzstanBaseSpider):
    name = "kyrgyzstan_akipress"

    country_code = 'KGZ'

    country = '吉尔吉斯斯坦'
    allowed_domains = []
    target_table = "kgz_akipress"
    start_urls = ["data:,kyrgyzstan_akipress_start"]
    source_urls = [
        "https://akipress.com/cat:14/",
        "https://akipress.com/cat:13/",
    ]

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing)

    def parse_listing(self, response):
        emitted = 0
        for source_url in self.source_urls:
            html = self._fetch_html(source_url)
            soup = BeautifulSoup(html, "html.parser")
            for node in soup.select(".listnews"):
                title_link = node.select_one("a.newstitle[href*='/news:']")
                href = (title_link.get("href") if title_link else "").strip()
                title = self._clean_text(title_link.get_text(" ", strip=True) if title_link else "")
                if not href or not title:
                    continue
                full_url = urljoin(source_url, href.split("?")[0])
                if full_url in self.seen_urls:
                    continue
                self.seen_urls.add(full_url)
                try:
                    detail_html = self._fetch_html(full_url)
                except Exception:
                    detail_html = ""
                if detail_html:
                    item = next(self.parse_detail(self._make_response(full_url, detail_html), fallback_title=title), None)
                else:
                    item = self._build_item(
                        response=self._make_response(full_url, ""),
                        title=title,
                        content=title,
                        publish_time=None,
                        author="AKIpress",
                        language="en",
                        section="economy",
                    )
                if item:
                    yield item
                    emitted += 1
                    if emitted >= 12:
                        return

    def parse_detail(self, response, fallback_title=""):
        title = self._clean_text(
            fallback_title
            or response.xpath("//meta[@property='og:title']/@content").get()
            or response.css("title::text").get()
        )
        title = re.sub(r"\s*-\s*AKIpress News Agency$", "", title).strip()
        if not title:
            return

        body_text = self._clean_text(" ".join(response.css("body ::text").getall()))
        publish_time = self._parse_datetime(
            self._extract_first_match(body_text, r"([A-Z][a-z]+ \d{1,2}, \d{4} / \d{1,2}:\d{2} [AP]M)"),
            languages=["en"],
        )
        if publish_time and not self.full_scan and publish_time < self.cutoff_date:
            return

        content = self._extract_teaser(body_text, title)
        if not content:
            content = self._clean_text(
                response.xpath("//meta[@property='og:description']/@content").get()
                or response.xpath("//meta[@name='og:description']/@content").get()
                or response.xpath("//meta[@name='description']/@content").get()
            )
        if not content:
            content = title

        yield self._build_item(
            response=response,
            title=title,
            content=content,
            publish_time=publish_time,
            author="AKIpress",
            language="en",
            section="economy",
        )

    def _extract_teaser(self, body_text, title):
        start = body_text.find(title)
        text = body_text[start:] if start >= 0 else body_text
        marker = "AKIPRESS.COM -"
        idx = text.find(marker)
        if idx >= 0:
            text = text[idx + len(marker):]
        for stop in ["To Read the Full Story", "Related content", "All rights reserved"]:
            pos = text.find(stop)
            if pos > 0:
                text = text[:pos]
        text = self._clean_text(text)
        if len(text) > 2000:
            text = text[:2000]
        if text == title:
            return ""
        return text

    def _extract_first_match(self, text, pattern):
        match = re.search(pattern, text)
        return match.group(1) if match else ""
