# 阿曼mtcit爬虫，负责抓取对应站点、机构或栏目内容。

import re

from bs4 import BeautifulSoup

import scrapy

from news_scraper.spiders.oman.base import OmanBaseSpider


# 阿曼政府类来源
# 站点：MTCIT
# 入库表：omn_mtcit
# 语言：英语


class OmanMtcitSpider(OmanBaseSpider):
    """阿曼交通通信与信息技术部新闻。

    站点：https://www.mtcit.gov.om
    栏目：Media -> News
    入库表：omn_mtcit
    """

    name = "oman_mtcit"


    country_code = 'OMN'


    country = '阿曼'
    allowed_domains = ["mtcit.gov.om", "www.mtcit.gov.om"]
    target_table = "omn_mtcit"
    start_urls = [
        "https://www.mtcit.gov.om/media-4/news-announcements-11/news-85",
    ]

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing, meta={"dont_verify_ssl": True})

    def parse_listing(self, response):
        links = response.css("a::attr(href)").getall()
        for href in links:
            full_url = response.urljoin(href)
            if "/media-4/news-announcements-11/news-85/" not in full_url or full_url in self.seen_urls:
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

        content = self._extract_content(response, title)
        if not content:
            return

        yield self._build_item(
            response=response,
            title=title.replace(" | MTCIT", "").strip(),
            content=content,
            publish_time=publish_time,
            author="MTCIT",
            language="en",
            section="news",
        )

    def _extract_publish_time(self, response):
        text = " ".join(response.xpath("//body//text()").getall())
        match = re.search(r"Date Published\s*:\s*([0-9]{1,2}\s+\w+\s+\d{4})", text)
        if not match:
            return None
        return self._parse_datetime(match.group(1), languages=["en"])

    def _extract_content(self, response, title):
        soup = BeautifulSoup(response.text, "html.parser")
        root = soup.select_one("main") or soup.select_one("article") or soup.body
        if not root:
            return ""

        for unwanted in root.select("script, style, nav, footer, header, aside, form, .share, .related"):
            unwanted.decompose()

        title_text = self._clean_text(title)
        parts = []
        for node in root.find_all(["p", "h2", "h3", "li"], recursive=True):
            text = self._clean_text(node.get_text(" ", strip=True))
            if not text or len(text) < 20:
                continue
            if text == title_text or text == "Read More":
                continue
            if text.startswith("Date Published"):
                continue
            if text not in parts:
                parts.append(text)

        return "\n\n".join(parts)
