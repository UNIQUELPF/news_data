# 澳大利亚treasury爬虫，负责抓取对应站点、机构或栏目内容。

import re

from bs4 import BeautifulSoup

import scrapy

from news_scraper.spiders.australia.base import AustraliaBaseSpider


class AustraliaTreasurySpider(AustraliaBaseSpider):
    name = "australia_treasury"

    country_code = 'AUS'

    country = '澳大利亚'
    allowed_domains = ["treasury.gov.au", "www.treasury.gov.au"]
    start_urls = [
        "https://treasury.gov.au/publication",
    ]

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing)

    def parse_listing(self, response):
        for href in response.css('a[href*="/publication/"]::attr(href)').getall():
            full_url = response.urljoin(href)
            if not self.should_process(full_url):
                continue
            if not self._should_fetch_url(full_url):
                continue
            yield scrapy.Request(full_url, callback=self.parse_detail)

    def parse_detail(self, response):
        title = self._clean_text(
            response.xpath("//meta[@property='og:title']/@content").get()
            or response.xpath("//meta[@name='dcterms.subject']/@content").get()
            or response.css("h1::text").get()
        )
        if not title:
            return

        publish_time = self._parse_datetime(
            response.xpath("//meta[@property='article:published_time']/@content").get()
            or response.css("time::attr(datetime), time::text").get()
            or response.xpath("//meta[@name='dcterms.date']/@content").get()
            or response.css(".published-date::text").get(),
            languages=["en"],
        )
        if publish_time and not self.full_scan and publish_time < self.cutoff_date:
            return

        content = self._extract_content(response, title)
        if not content:
            content = self._clean_text(
                response.xpath("//meta[@name='description']/@content").get()
                or response.xpath("//meta[@name='dcterms.description']/@content").get()
            )
        if not content:
            return

        section = "publication"
        yield self._build_item(
            response=response,
            title=title,
            content=content,
            publish_time=publish_time,
            author="Australian Treasury",
            language="en",
            section=section,
        )

    def _extract_content(self, response, title):
        soup = BeautifulSoup(response.text, "html.parser")
        root = soup.select_one("article") or soup.select_one("main")
        if not root:
            return ""

        for unwanted in root.select("script, style, nav, footer, header, aside, form, .share, .related"):
            unwanted.decompose()

        title_text = self._clean_text(title)
        parts = []
        for node in root.find_all(["p", "h2", "h3", "li"], recursive=True):
            text = self._clean_text(node.get_text(" ", strip=True))
            if not text or len(text) < 25 or text == title_text:
                continue
            if text not in parts:
                parts.append(text)
        if parts:
            return "\n\n".join(parts)

        fallback = self._clean_text(root.get_text(" ", strip=True))
        if fallback.startswith(title_text):
            fallback = self._clean_text(fallback[len(title_text):])
        return fallback

    def _should_fetch_url(self, url):
        if self.full_scan:
            return True
        match = re.search(r"/publication/(?:p)?(20\d{2})", url)
        if not match:
            return True
        return int(match.group(1)) >= self.cutoff_date.year
