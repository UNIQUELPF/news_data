# 比利时economie gov爬虫，负责抓取对应站点、机构或栏目内容。

from bs4 import BeautifulSoup

import scrapy

from news_scraper.spiders.belgium.base import BelgiumBaseSpider


class BelgiumEconomieGovSpider(BelgiumBaseSpider):
    name = "belgium_economie_gov"

    country_code = 'BEL'

    country = '比利时'
    allowed_domains = ["economie.fgov.be"]
    target_table = "bel_economie_gov"
    start_urls = ["https://economie.fgov.be/en/news"]

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing)

    def parse_listing(self, response):
        for href in response.css("a[href^='/en/news/']::attr(href)").getall():
            full_url = response.urljoin(href)
            if full_url.rstrip("/") == self.start_urls[0].rstrip("/") or full_url in self.seen_urls:
                continue
            self.seen_urls.add(full_url)
            yield scrapy.Request(full_url, callback=self.parse_detail)

    def parse_detail(self, response):
        title = self._clean_text(
            response.css("h1::text").get()
            or response.xpath("//meta[@property='og:title']/@content").get()
            or response.css("title::text").get()
        )
        if not title:
            return

        publish_time = self._parse_datetime(
            self._clean_text(" ".join(response.css("main ::text").getall()[:120])),
            languages=["en"],
        )
        if publish_time and not self.full_scan and publish_time < self.cutoff_date:
            return

        content = self._extract_content(response)
        if not content:
            return

        yield self._build_item(
            response=response,
            title=title,
            content=content,
            publish_time=publish_time,
            author="FPS Economy",
            language="en",
            section="economy",
        )

    def _extract_content(self, response):
        soup = BeautifulSoup(response.text, "html.parser")
        root = soup.select_one(".field--name-body") or soup.select_one("article") or soup.select_one(".node")
        if not root:
            return ""
        for unwanted in root.select("script, style, nav, footer, header, aside, form"):
            unwanted.decompose()
        parts = []
        for node in root.find_all(["p", "li"], recursive=True):
            text = self._clean_text(node.get_text(" ", strip=True))
            if not text or len(text) < 25 or text.startswith("Last update"):
                continue
            if text not in parts:
                parts.append(text)
        return "\n\n".join(parts)

