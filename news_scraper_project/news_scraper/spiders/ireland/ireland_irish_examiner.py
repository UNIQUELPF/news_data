# 爱尔兰irish examiner爬虫，负责抓取对应站点、机构或栏目内容。

from bs4 import BeautifulSoup

import scrapy

from news_scraper.spiders.ireland.base import IrelandBaseSpider


class IrelandIrishExaminerSpider(IrelandBaseSpider):
    """爱尔兰考察报商业栏目。

    类型：经济类
    站点：https://www.irishexaminer.com/business/
    入库表：irl_irish_examiner
    """

    name = "ireland_irish_examiner"
    allowed_domains = ["irishexaminer.com", "www.irishexaminer.com"]
    # 经济类：商业新闻媒体表
    target_table = "irl_irish_examiner"
    start_urls = [
        "https://www.irishexaminer.com/business/",
    ]

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing)

    def parse_listing(self, response):
        # 经济类列表页：抓 business 频道下带 arid 标识的文章。
        links = response.css('a[href*="/business/"][href*="/arid-"]::attr(href)').getall()
        for href in links:
            full_url = response.urljoin(href)
            if full_url in self.seen_urls:
                continue
            self.seen_urls.add(full_url)
            yield scrapy.Request(full_url, callback=self.parse_detail)

    def parse_detail(self, response):
        # 经济类详情页：过滤 410 等无效文章，只保留正常正文。
        if response.status != 200:
            return

        title = self._clean_text(
            response.xpath("//meta[@property='og:title']/@content").get()
            or response.css("h1::text").get()
        )
        if not title or "Gone - Irish Examiner" in title:
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
            title=title,
            content=content,
            publish_time=publish_time,
            author=self._clean_text(response.xpath("//meta[@name='author']/@content").get()) or "Irish Examiner",
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
