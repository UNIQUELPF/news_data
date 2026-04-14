# 奥地利diepresse爬虫，负责抓取对应站点、机构或栏目内容。

import re

from bs4 import BeautifulSoup

import scrapy

from news_scraper.spiders.austria.base import AustriaBaseSpider


# 奥地利经济类来源
# 站点：Die Presse
# 入库表：aut_diepresse
# 语言：德语


class AustriaDiePresseSpider(AustriaBaseSpider):
    name = "austria_diepresse"

    country_code = 'AUT'

    country = '奥地利'
    allowed_domains = ["diepresse.com", "www.diepresse.com"]
    target_table = "aut_diepresse"
    start_urls = [
        "https://www.diepresse.com/wirtschaft",
    ]

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing)

    def parse_listing(self, response):
        links = response.css('a[href*="diepresse.com/"]::attr(href)').getall()
        for href in links:
            full_url = response.urljoin(href)
            if full_url in self.seen_urls:
                continue
            if not full_url.startswith("https://www.diepresse.com/"):
                continue
            if not re.search(r"https://www\.diepresse\.com/\d+/", full_url):
                continue
            self.seen_urls.add(full_url)
            yield scrapy.Request(full_url, callback=self.parse_detail)

    def parse_detail(self, response):
        section_path = response.xpath("//meta[@name='section-path']/@content").get() or ""
        if "/wirtschaft/" not in section_path:
            return

        title = self._clean_text(
            response.xpath("//meta[@property='og:title']/@content").get()
            or response.css("h1::text").get()
        )
        if not title:
            return

        publish_time = self._parse_datetime(
            response.xpath("//meta[@property='article:published_time']/@content").get()
            or response.xpath("//time/@datetime").get()
            or response.xpath("//time/text()").get(),
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
            author="Die Presse",
            language="de",
            section="wirtschaft",
        )

    def _extract_content(self, response):
        soup = BeautifulSoup(response.text, "html.parser")
        root = (
            soup.select_one("article")
            or soup.select_one("[itemprop='articleBody']")
            or soup.select_one("main")
        )
        if not root:
            return ""

        for unwanted in root.select("script, style, nav, footer, header, aside, form, .share, .related, .paywall"):
            unwanted.decompose()

        parts = []
        for node in root.find_all(["p", "h2", "h3", "li"], recursive=True):
            text = self._clean_text(node.get_text(" ", strip=True))
            if not text or len(text) < 30:
                continue
            if text not in parts:
                parts.append(text)
        return "\n\n".join(parts)
