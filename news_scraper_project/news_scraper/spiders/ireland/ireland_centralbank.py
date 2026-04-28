# 爱尔兰centralbank爬虫，负责抓取对应站点、机构或栏目内容。

from bs4 import BeautifulSoup

import scrapy

from news_scraper.spiders.ireland.base import IrelandBaseSpider


class IrelandCentralBankSpider(IrelandBaseSpider):
    """爱尔兰中央银行新闻稿。

    类型：政府/监管类
    站点：https://www.centralbank.ie/news-media/press-releases
    入库表：irl_centralbank
    """

    name = "ireland_centralbank"


    country_code = 'IRL'


    country = '爱尔兰'
    allowed_domains = ["centralbank.ie", "www.centralbank.ie"]
    # 政府/监管类：中央银行官方新闻与监管信息表
    start_urls = [
        "https://www.centralbank.ie/news-media/press-releases",
    ]

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing)

    def parse_listing(self, response):
        # 政府/监管类列表页：抓新闻稿列表中的 article 详情页。
        links = response.css('a[href*="/news/article/"]::attr(href)').getall()
        for href in links:
            full_url = response.urljoin(href)
            if not self.should_process(full_url):
                continue
            yield scrapy.Request(full_url, callback=self.parse_detail)

        next_page = response.css('a[aria-label="Next page"]::attr(href), a[href*="/news-media/press-releases/"]::attr(href)').getall()
        for href in next_page:
            full_url = response.urljoin(href)
            if "/news-media/press-releases/" not in full_url or not self.should_process(full_url):
                continue
            yield scrapy.Request(full_url, callback=self.parse_listing)

    def parse_detail(self, response):
        # 政府/监管类详情页：提取央行新闻稿、讲话和公告正文。
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
            title=title,
            content=content,
            publish_time=publish_time,
            author="Central Bank of Ireland",
            language="en",
            section="press-release",
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
            if not text or len(text) < 30:
                continue
            if text not in parts:
                parts.append(text)
        return "\n\n".join(parts)
