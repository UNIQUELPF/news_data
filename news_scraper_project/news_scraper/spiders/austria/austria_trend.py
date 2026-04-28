# 奥地利trend爬虫，负责抓取对应站点、机构或栏目内容。

from bs4 import BeautifulSoup

import scrapy

from news_scraper.spiders.austria.base import AustriaBaseSpider


# 奥地利经济类来源
# 站点：trend
# 入库表：aut_trend
# 语言：德语


class AustriaTrendSpider(AustriaBaseSpider):
    name = "austria_trend"

    country_code = 'AUT'

    country = '奥地利'
    allowed_domains = ["trend.at", "www.trend.at"]
    start_urls = [
        "https://www.trend.at/unternehmen",
    ]

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing)

    def parse_listing(self, response):
        links = response.css('a[href*="trend.at/unternehmen/"]::attr(href), a[href*="trend.at/finanzen/"]::attr(href)').getall()
        for href in links:
            full_url = response.urljoin(href)
            if not self.should_process(full_url):
                continue
            if "/unternehmen/" not in full_url and "/finanzen/" not in full_url:
                continue
            yield scrapy.Request(full_url, callback=self.parse_detail)

        next_page = response.css("a[rel='next']::attr(href)").get()
        if next_page:
            yield response.follow(next_page, callback=self.parse_listing)

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

        section = "finanzen" if "/finanzen/" in response.url else "unternehmen"
        yield self._build_item(
            response=response,
            title=title,
            content=content,
            publish_time=publish_time,
            author="trend",
            language="de",
            section=section,
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

