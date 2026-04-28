# 澳大利亚rba爬虫，负责抓取对应站点、机构或栏目内容。

import re

from bs4 import BeautifulSoup

import scrapy

from news_scraper.spiders.australia.base import AustraliaBaseSpider


class AustraliaRbaSpider(AustraliaBaseSpider):
    name = "australia_rba"

    country_code = 'AUS'

    country = '澳大利亚'
    allowed_domains = ["rba.gov.au", "www.rba.gov.au"]
    start_urls = [
        "https://www.rba.gov.au/media-releases/",
        "https://www.rba.gov.au/speeches/",
    ]

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing)

    def parse_listing(self, response):
        for href in response.css("a::attr(href)").getall():
            full_url = response.urljoin(href)
            if not self.should_process(full_url):
                continue
            if "/media-releases/" not in full_url and "/speeches/" not in full_url:
                continue
            if not full_url.endswith(".html"):
                continue
            if not self._should_fetch_url(full_url):
                continue
            yield scrapy.Request(full_url, callback=self.parse_detail)

    def parse_detail(self, response):
        title = self._clean_text(
            response.xpath("//meta[@property='og:title']/@content").get()
            or response.css("h1::text").get()
        )
        if not title:
            return

        publish_time = self._parse_datetime(
            response.xpath("//meta[@property='article:published_time']/@content").get()
            or response.css("time::attr(datetime), time::text").get()
            or response.css(".date::text").get(),
            languages=["en"],
        )
        if publish_time and not self.full_scan and publish_time < self.cutoff_date:
            return

        content = self._extract_content(response, title)
        if not content:
            content = self._clean_text(response.xpath("//meta[@name='description']/@content").get())
        if not content:
            return

        section = "speech" if "/speeches/" in response.url else "media-release"
        yield self._build_item(
            response=response,
            title=title,
            content=content,
            publish_time=publish_time,
            author="Reserve Bank of Australia",
            language="en",
            section=section,
        )

    def _extract_content(self, response, title):
        soup = BeautifulSoup(response.text, "html.parser")
        root = soup.select_one("main") or soup.select_one("article") or soup.select_one("#content")
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
        return "\n\n".join(parts)

    def _should_fetch_url(self, url):
        if self.full_scan:
            return True
        match = re.search(r"/(20\d{2})/", url)
        if not match:
            return True
        return int(match.group(1)) >= self.cutoff_date.year
