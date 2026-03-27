from bs4 import BeautifulSoup

import scrapy

from news_scraper.spiders.austria.base import AustriaBaseSpider


# 奥地利政府类来源
# 站点：BMAW
# 入库表：aut_bmaw
# 语言：德语


class AustriaBmawSpider(AustriaBaseSpider):
    name = "austria_bmaw"
    allowed_domains = ["bmaw.gv.at", "www.bmaw.gv.at", "bmwet.gv.at", "www.bmwet.gv.at"]
    target_table = "aut_bmaw"
    start_urls = [
        "https://www.bmaw.gv.at/Presse/AktuellePressemeldungen.html",
    ]

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing)

    def parse_listing(self, response):
        links = response.css('a[href*="/Presse/AktuellePressemeldungen/"]::attr(href)').getall()
        for href in links:
            full_url = response.urljoin(href)
            if full_url.endswith("AktuellePressemeldungen.html") or full_url in self.seen_urls:
                continue
            if not full_url.endswith(".html"):
                continue
            self.seen_urls.add(full_url)
            yield scrapy.Request(full_url, callback=self.parse_detail)

        archive_links = response.css('a[href*="/Presse/Archiv/"]::attr(href)').getall()
        for href in archive_links:
            full_url = response.urljoin(href)
            if full_url in self.seen_urls:
                continue
            self.seen_urls.add(full_url)
            yield scrapy.Request(full_url, callback=self.parse_archive)

    def parse_archive(self, response):
        links = response.css('a[href*="/Presse/AktuellePressemeldungen/"]::attr(href), a[href*="/Presse/Archiv/"]::attr(href)').getall()
        for href in links:
            full_url = response.urljoin(href)
            if not full_url.endswith(".html") or full_url in self.seen_urls:
                continue
            if "/Presse/AktuellePressemeldungen/" in full_url:
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
            or response.re_first(r"(\d{4}-\d{2}-\d{2})"),
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
            author="BMAW",
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
