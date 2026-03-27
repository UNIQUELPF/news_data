from bs4 import BeautifulSoup

import scrapy

from news_scraper.spiders.ireland.base import IrelandBaseSpider


class IrelandFinanceGovSpider(IrelandBaseSpider):
    """爱尔兰财政部新闻与新闻稿。

    类型：政府类
    站点：https://www.gov.ie/en/department-of-finance/
    入库表：irl_finance_gov
    """

    name = "ireland_finance_gov"
    allowed_domains = ["gov.ie", "www.gov.ie"]
    # 政府类：财政部官方新闻/公告表
    target_table = "irl_finance_gov"
    start_urls = [
        "https://www.gov.ie/en/department-of-finance/",
    ]

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing)

    def parse_listing(self, response):
        # 政府类列表页：只保留财政部自己的新闻稿和出版物链接。
        links = response.css("a::attr(href)").getall()
        for href in links:
            full_url = response.urljoin(href)
            if "/department-of-finance/" not in full_url:
                continue
            if "/press-releases/" not in full_url and "/publications/" not in full_url:
                continue
            if full_url in self.seen_urls:
                continue
            self.seen_urls.add(full_url)
            yield scrapy.Request(full_url, callback=self.parse_detail)

    def parse_detail(self, response):
        # 政府类详情页：正文通常在 main 容器中，按官方发布时间做增量。
        title = self._clean_text(
            response.xpath("//meta[@property='og:title']/@content").get()
            or response.css("h1::text").get()
        )
        if not title:
            return

        publish_time = self._parse_datetime(
            "".join(response.xpath("//text()[contains(., 'Published on:')]/following::text()[1]").getall())
            or response.css("time::attr(datetime), time::text").get(),
            languages=["en"],
        )
        if publish_time and not self.full_scan and publish_time < self.cutoff_date:
            return

        content = self._extract_content(response)
        if not content:
            return

        # 政府类细分：press-release 表示新闻稿，publication 表示政策/报告类内容。
        section = "press-release" if "/press-releases/" in response.url else "publication"
        yield self._build_item(
            response=response,
            title=title,
            content=content,
            publish_time=publish_time,
            author="Department of Finance",
            language="en",
            section=section,
        )

    def _extract_content(self, response):
        soup = BeautifulSoup(response.text, "html.parser")
        root = soup.select_one("main") or soup.select_one("article")
        if not root:
            return ""

        for unwanted in root.select("script, style, nav, footer, header, aside, form, .share, .related"):
            unwanted.decompose()

        parts = []
        for node in root.find_all(["p", "h2", "h3", "li"], recursive=True):
            text = self._clean_text(node.get_text(" ", strip=True))
            if not text or len(text) < 25:
                continue
            if text not in parts:
                parts.append(text)
        return "\n\n".join(parts)
