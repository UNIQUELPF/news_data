# 奥地利bmf爬虫，负责抓取对应站点、机构或栏目内容。

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

    country_code = 'AUT'

    country = '奥地利'
    allowed_domains = ["bmf.gv.at", "www.bmf.gv.at"]
    start_urls = [
        "https://www.bmf.gv.at/presse/pressemeldungen/2026.html",
    ]

    fallback_content_selector = "article, main"
    strict_date_required = False

    async def start(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing, dont_filter=True)

    def parse_listing(self, response):
        if self._stop_pagination:
            return

        links = response.css('a[href*="/presse/pressemeldungen/"]::attr(href)').getall()
        has_valid_item_in_window = False
        for href in links:
            full_url = response.urljoin(href)
            if not self.should_process(full_url):
                continue
            if not full_url.endswith(".html"):
                continue
            if full_url.endswith("/2026.html") or "/2026/" not in full_url:
                yield scrapy.Request(full_url, callback=self.parse_listing)
                continue
            has_valid_item_in_window = True
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
        if not self.should_process(response.url, publish_time):
            self._stop_pagination = True
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
