# 爱尔兰irish times爬虫，负责抓取对应站点、机构或栏目内容。

import re

from bs4 import BeautifulSoup

import scrapy

from news_scraper.spiders.ireland.base import IrelandBaseSpider


class IrelandIrishTimesSpider(IrelandBaseSpider):
    """爱尔兰时报商业栏目。

    类型：经济类
    站点：https://www.irishtimes.com/business/
    入库表：irl_irish_times
    """

    name = "ireland_irish_times"


    country_code = 'IRL'


    country = '爱尔兰'
    allowed_domains = ["irishtimes.com", "www.irishtimes.com"]
    # 经济类：商业新闻媒体表
    target_table = "irl_irish_times"
    start_urls = [
        "https://www.irishtimes.com/business/",
    ]

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing)

    def parse_listing(self, response):
        # 经济类列表页：只保留带具体年月日路径的文章，排除栏目分页。
        links = response.css('a[href*="/business/"]::attr(href)').getall()
        for href in links:
            full_url = response.urljoin(href)
            if "/business/" not in full_url or full_url in self.seen_urls:
                continue
            if not re.search(r"/business/\d{4}/\d{2}/\d{2}/", full_url):
                continue
            self.seen_urls.add(full_url)
            yield scrapy.Request(full_url, callback=self.parse_detail)

    def parse_detail(self, response):
        # 经济类详情页：提取正文级内容，避免只存摘要。
        title = self._clean_text(
            response.xpath("//meta[@property='og:title']/@content").get()
            or response.css("h1::text").get()
        )
        if not title:
            return

        publish_time = self._parse_datetime(
            response.css("time::attr(datetime), time::text").get()
            or response.xpath("//meta[@property='article:published_time']/@content").get(),
            languages=["en"],
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
            title=title.replace(" – The Irish Times", "").strip(),
            content=content,
            publish_time=publish_time,
            author=self._clean_text(response.xpath("//meta[@name='author']/@content").get()) or "The Irish Times",
            language="en",
            section="business",
        )

    def _extract_content(self, response):
        soup = BeautifulSoup(response.text, "html.parser")
        root = soup.select_one("article") or soup.select_one("main")
        if not root:
            return ""

        for unwanted in root.select("script, style, nav, footer, header, aside, form, .share, .related"):
            unwanted.decompose()

        parts = []
        for node in root.find_all(["p", "h2", "h3", "li"], recursive=True):
            text = self._clean_text(node.get_text(" ", strip=True))
            if not text or len(text) < 35:
                continue
            if text not in parts:
                parts.append(text)
        return "\n\n".join(parts)
