# 奥地利oenb爬虫，负责抓取对应站点、机构或栏目内容。

import re

from bs4 import BeautifulSoup

import scrapy

from news_scraper.spiders.austria.base import AustriaBaseSpider


# 奥地利政府/监管类来源
# 站点：OeNB
# 入库表：aut_oenb
# 语言：德语


class AustriaOenbSpider(AustriaBaseSpider):
    name = "austria_oenb"

    country_code = 'AUT'

    country = '奥地利'
    allowed_domains = ["oenb.at", "www.oenb.at"]
    start_urls = [
        "https://www.oenb.at/Presse.html",
    ]

    fallback_content_selector = "article, main"

    async def start(self):
        self._stop_pagination = False
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing, dont_filter=True)

    def parse_listing(self, response):
        if self._stop_pagination:
            return
        links = response.css('a[href*="/Presse/Pressearchiv/"]::attr(href)').getall()
        has_valid_item_in_window = self.full_scan
        for href in links:
            full_url = response.urljoin(href)
            if not full_url.endswith(".html"):
                continue
            date_match = re.search(r"/Pressearchiv/(\d{4})(\d{2})(\d{2})\.html", full_url)
            publish_time = None
            if date_match:
                publish_time = self._parse_datetime(f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}", languages=["de", "en"])
            if not self.should_process(full_url, publish_time):
                continue
            has_valid_item_in_window = True
            yield scrapy.Request(full_url, callback=self.parse_detail)
        if not has_valid_item_in_window:
            self._stop_pagination = True

        archive_page = response.css('a[href*="/Presse/Pressearchiv.html"]::attr(href)').get()
        if archive_page:
            full_archive = response.urljoin(archive_page)
            if self.should_process(full_archive):
                yield scrapy.Request(full_archive, callback=self.parse_archive)

    def parse_archive(self, response):
        if self._stop_pagination:
            return
        links = response.css('a[href*="/Presse/Pressearchiv/"]::attr(href)').getall()
        for href in links:
            full_url = response.urljoin(href)
            if not full_url.endswith(".html"):
                continue
            date_match = re.search(r"/Pressearchiv/(\d{4})(\d{2})(\d{2})\.html", full_url)
            publish_time = None
            if date_match:
                publish_time = self._parse_datetime(f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}", languages=["de", "en"])
            if not self.should_process(full_url, publish_time):
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
            or response.xpath("//time/@datetime").get()
            or response.xpath("//time/text()").get()
            or response.re_first(r"/Pressearchiv/(\d{4})(\d{2})(\d{2})\.html"),
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
            author="OeNB",
            language="de",
            section="press",
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

