import re

from bs4 import BeautifulSoup

import scrapy

from news_scraper.spiders.austria.base import AustriaBaseSpider


# 奥地利政府类来源
# 站点：BMF
# 入库表：aut_bmf
# 语言：德语


class AustriaBmfSpider(AustriaBaseSpider):
    name = "austria_bmf"
    allowed_domains = ["bmf.gv.at", "www.bmf.gv.at"]
    target_table = "aut_bmf"
    start_urls = [
        "https://www.bmf.gv.at/presse/pressemeldungen/2026.html",
    ]

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing)

    def parse_listing(self, response):
        links = response.css('a[href*="/presse/pressemeldungen/"]::attr(href)').getall()
        for href in links:
            full_url = response.urljoin(href)
            if full_url in self.seen_urls:
                continue
            if not full_url.endswith(".html"):
                continue
            if full_url.endswith("/2026.html") or "/2026/" not in full_url:
                self.seen_urls.add(full_url)
                yield scrapy.Request(full_url, callback=self.parse_listing)
                continue
            self.seen_urls.add(full_url)
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
            or response.xpath("//time/@datetime").get()
            or response.xpath("//time/text()").get()
            or re.search(r"(\d{4}-\d{2}-\d{2})", response.text).group(1) if re.search(r"(\d{4}-\d{2}-\d{2})", response.text) else None,
            languages=["de", "en"],
        )
        if publish_time and not self.full_scan and publish_time < self.cutoff_date:
            return

        content = self._extract_content(response)
        if not content:
            content = self._clean_text(response.xpath("//meta[@name='description']/@content").get())
        if not content:
            return

        yield self._build_item(
            response=response,
            title=title,
            content=content,
            publish_time=publish_time,
            author="BMF",
            language="de",
            section="press-release",
        )

    def _extract_content(self, response):
        soup = BeautifulSoup(response.text, "html.parser")
        root = soup.select_one("article") or soup.select_one("main") or soup.select_one("#content")
        if not root:
            return ""

        for unwanted in root.select("script, style, nav, footer, header, aside, form"):
            unwanted.decompose()

        parts = []
        for node in root.find_all(["p", "h2", "h3", "li"], recursive=True):
            text = self._clean_text(node.get_text(" ", strip=True))
            if not text or len(text) < 30:
                continue
            if text not in parts:
                parts.append(text)
        return "\n\n".join(parts)
