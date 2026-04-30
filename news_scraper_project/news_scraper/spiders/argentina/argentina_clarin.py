# 阿根廷clarin爬虫，负责抓取对应站点、机构或栏目内容。

from datetime import datetime

import dateparser
import scrapy
from news_scraper.spiders.smart_spider import SmartSpider
from bs4 import BeautifulSoup
from news_scraper.items import NewsItem

# 阿根廷经济类来源
# 站点：Clarin
# 入库表：arg_clarin
# 语言：西班牙语


class ArgentinaClarinSpider(SmartSpider):
    """阿根廷 Clarin 爬虫。

    抓取站点：https://www.clarin.com
    抓取栏目：economia
    入库表：arg_clarin
    语言：西班牙语
    """

    name = "argentina_clarin"


    country_code = "ARG"


    country = "阿根廷"
    language = "en"
    source_timezone = "America/Argentina/Buenos_Aires"
    start_date = "2026-01-01"
    allowed_domains = ["clarin.com"]
    # 当前 spider 对应的数据库表名。

    # Clarín 的经济栏目页能直接拿到文章链接。
    start_urls = [
        "https://www.clarin.com/economia/",
    ]

    # 首次抓取的默认时间边界；后续优先按数据库里最新时间做增量。

    custom_settings = {
        "DOWNLOAD_DELAY": 0.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 8,
    }
    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing)

    def parse_listing(self, response):
        # 列表页只保留经济频道详情链接。
        article_links = response.css('a[href*="/economia/"]::attr(href)').getall()

        for href in article_links:
            full_url = response.urljoin(href)
            if not self.should_process(full_url):
                continue
            if "/economia/" not in full_url or not full_url.endswith(".html"):
                continue
            yield scrapy.Request(full_url, callback=self.parse_detail)

    def parse_detail(self, response):
        # 详情页正文直接从 article/main 的段落提取。
        title = self._clean_text(
            response.xpath("//meta[@property='og:title']/@content").get()
            or response.css("h1::text").get()
        )
        if not title:
            return

        publish_time = self._parse_datetime(
            response.xpath("//meta[@property='article:published_time']/@content").get()
            or response.xpath("//meta[@name='date']/@content").get()
        )
        if publish_time and not self.full_scan and publish_time < self.cutoff_date:
            return

        content = self._extract_content(response)
        if not content:
            content = self._clean_text(response.xpath("//meta[@property='og:description']/@content").get())
        if not content:
            return

        author = self._clean_text(
            response.xpath("//meta[@name='author']/@content").get()
        ) or "Clarin"

        item = NewsItem()
        item["url"] = response.url
        item["title"] = title
        item["content"] = content
        item["publish_time"] = publish_time or datetime.now()
        item["author"] = author
        item["language"] = "es"
        item["section"] = "economia"
        item["scrape_time"] = datetime.now()
        yield item

    def _extract_content(self, response):
        soup = BeautifulSoup(response.text, "html.parser")
        root = soup.select_one("article") or soup.select_one("main")
        if not root:
            return ""

        for unwanted in root.select(
            "script, style, nav, footer, header, aside, form, figure, .paywall, .related, .social-share"
        ):
            unwanted.decompose()

        parts = []
        for node in root.find_all(["p", "h2", "h3", "li"], recursive=True):
            text = self._clean_text(node.get_text(" ", strip=True))
            if not text or len(text) < 30:
                continue
            if "Para disfrutar los contenidos de Clarín" in text:
                continue
            if text not in parts:
                parts.append(text)

        return "\n\n".join(parts)

    def _parse_datetime(self, value):
        if not value:
            return None
        parsed = dateparser.parse(value, languages=["es"], settings={"TIMEZONE": "UTC"})
        if not parsed:
            return None
        return parsed.replace(tzinfo=None)

    def _clean_text(self, value):
        if not value:
            return ""
        return " ".join(str(value).split()).strip()
