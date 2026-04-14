# 阿曼news爬虫，负责抓取对应站点、机构或栏目内容。

import re

from bs4 import BeautifulSoup

import scrapy

from news_scraper.spiders.oman.base import OmanBaseSpider


# 阿曼官方通讯社/经济类来源
# 站点：Oman News Agency
# 入库表：omn_oman_news
# 语言：阿拉伯语


class OmanNewsSpider(OmanBaseSpider):
    """阿曼通讯社经济栏目。

    站点：https://www.omannews.gov.om
    栏目：topics/ar/7（经济）
    入库表：omn_oman_news
    """

    name = "oman_news"


    country_code = 'OMN'


    country = '阿曼'
    allowed_domains = ["omannews.gov.om", "www.omannews.gov.om"]
    target_table = "omn_oman_news"
    start_urls = [
        "https://www.omannews.gov.om/topics/ar/7",
    ]

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing, meta={"dont_verify_ssl": True})

    def parse_listing(self, response):
        links = response.css("a::attr(href)").getall()
        for href in links:
            full_url = response.urljoin(href)
            if "/topics/ar/7/show/" not in full_url or full_url in self.seen_urls:
                continue
            self.seen_urls.add(full_url)
            yield scrapy.Request(full_url, callback=self.parse_detail, meta={"dont_verify_ssl": True})

    def parse_detail(self, response):
        title = self._clean_text(
            response.xpath("//meta[@property='og:title']/@content").get()
            or response.css("h1::text").get()
        )
        if not title:
            return

        publish_time = self._extract_publish_time(response)
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
            author="Oman News Agency",
            language="ar",
            section="economy",
        )

    def _extract_publish_time(self, response):
        text = " ".join(response.xpath("//body//text()").getall())
        match = re.search(r"\b(\d{1,2}\s+\S+\s+\d{4})\b", text)
        if not match:
            return None
        return self._parse_datetime(match.group(1), languages=["ar"])

    def _extract_content(self, response):
        soup = BeautifulSoup(response.text, "html.parser")
        root = soup.select_one(".post-content") or soup.select_one("article") or soup.select_one("main")
        if not root:
            return ""

        for unwanted in root.select("script, style, nav, footer, header, aside, form, .share, .related"):
            unwanted.decompose()

        parts = []
        for node in root.find_all(["p", "h2", "h3", "li"], recursive=True):
            text = self._clean_text(node.get_text(" ", strip=True))
            if not text or len(text) < 20:
                continue
            if text not in parts:
                parts.append(text)
        return "\n\n".join(parts)
