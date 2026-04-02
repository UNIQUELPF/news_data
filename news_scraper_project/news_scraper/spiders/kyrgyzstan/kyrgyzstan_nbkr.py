# 吉尔吉斯斯坦国家银行英文新闻爬虫，抓取央行新闻与公告。

import re
from urllib.parse import urljoin

import scrapy
from bs4 import BeautifulSoup

from news_scraper.spiders.kyrgyzstan.base import KyrgyzstanBaseSpider


class KyrgyzstanNbkrSpider(KyrgyzstanBaseSpider):
    name = "kyrgyzstan_nbkr"
    allowed_domains = []
    target_table = "kgz_nbkr"
    start_urls = ["data:,kyrgyzstan_nbkr_start"]
    source_urls = [
        "https://www.nbkr.kg/index1.jsp?item=2546&lang=ENG",
    ]

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing)

    def parse_listing(self, response):
        emitted = 0
        for source_url in self.source_urls:
            html = self._fetch_html(source_url)
            soup = BeautifulSoup(html, "html.parser")
            root = soup.select_one(".content-text")
            if not root:
                continue
            for link in root.select("a[href$='.pdf']"):
                href = (link.get("href") or "").strip()
                title = self._clean_text(link.get_text(" ", strip=True))
                if not title or not href:
                    continue
                full_url = urljoin(source_url, href.replace("&amp;", "&"))
                if full_url in self.seen_urls:
                    continue
                self.seen_urls.add(full_url)
                item = next(self.parse_detail(scrapy.Request(url=full_url), fallback_title=title), None)
                if item:
                    yield item
                    emitted += 1
                    if emitted >= 8:
                        return

    def parse_detail(self, response, fallback_title=""):
        title = self._clean_text(fallback_title)
        if not title:
            return

        publish_time = self._parse_datetime(
            self._extract_first_match(title, r"(\d{2}\.\d{2}\.\d{4})"),
            languages=["en"],
        )
        if publish_time and not self.full_scan and publish_time < self.cutoff_date:
            return

        content = self._extract_pdf_text(response.url)
        if not content:
            content = title

        yield self._build_item(
            response=response,
            title=title,
            content=content,
            publish_time=publish_time,
            author="National Bank of the Kyrgyz Republic",
            language="en",
            section="central-bank",
        )

    def _extract_first_match(self, text, pattern):
        match = re.search(pattern, text, flags=re.IGNORECASE)
        return match.group(1) if match else ""
