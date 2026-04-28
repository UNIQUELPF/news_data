# 阿根廷lanacion爬虫，负责抓取对应站点、机构或栏目内容。

from datetime import datetime
from email.utils import parsedate_to_datetime

import scrapy
from news_scraper.spiders.smart_spider import SmartSpider
from bs4 import BeautifulSoup
from news_scraper.items import NewsItem

# 阿根廷经济类来源
# 站点：La Nacion
# 入库表：arg_lanacion
# 语言：西班牙语


class ArgentinaLaNacionSpider(SmartSpider):
    """阿根廷 La Nacion 爬虫。

    抓取站点：https://www.lanacion.com.ar
    抓取入口：Economia RSS
    入库表：arg_lanacion
    语言：西班牙语
    """

    name = "argentina_lanacion"


    country_code = "ARG"


    country = "阿根廷"
    language = "en"
    source_timezone = "America/Argentina/Buenos_Aires"
    start_date = "2026-01-01"
    allowed_domains = ["lanacion.com.ar"]
    # 当前 spider 对应的数据库表名。

    # La Nacion 经济页详情经常被付费墙截断，RSS 正文反而更稳定。
    start_urls = [
        "https://www.lanacion.com.ar/arc/outboundfeeds/rss/category/economia/",
    ]

    # 首次抓取的默认时间边界；后续优先按数据库里最新时间做增量。

    custom_settings = {
        "DOWNLOAD_DELAY": 0.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 8,
    }


    @classmethod


    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_feed)

    def parse_feed(self, response):
        # 直接从经济 RSS 读取标题、时间、正文和作者，绕开付费墙干扰。
        for item in response.xpath("//channel/item"):
            url = item.xpath("./link/text()").get()
            if not url or not self.should_process(url):
                continue
            if "/economia/" not in url:
                continue

            publish_time = self._parse_rss_datetime(item.xpath("./pubDate/text()").get())
            if publish_time and not self.full_scan and publish_time < self.cutoff_date:
                continue

            title = self._clean_text(item.xpath("./title/text()").get())
            content = self._clean_html(
                item.xpath("./content:encoded/text()", namespaces={"content": "http://purl.org/rss/1.0/modules/content/"}).get()
                or item.xpath("./description/text()").get()
            )
            if not title or not content:
                continue

            author = self._clean_text(
                item.xpath("./dc:creator/text()", namespaces={"dc": "http://purl.org/dc/elements/1.1/"}).get()
            ) or "La Nacion"

            news_item = NewsItem()
            news_item["url"] = url
            news_item["title"] = title
            news_item["content"] = content
            news_item["publish_time"] = publish_time or datetime.now()
            news_item["author"] = author
            news_item["language"] = "es"
            news_item["section"] = "economia"
            news_item["scrape_time"] = datetime.now()
            yield news_item

    def _parse_rss_datetime(self, value):
        if not value:
            return None
        try:
            return parsedate_to_datetime(value).replace(tzinfo=None)
        except Exception:
            return None

    def _clean_html(self, value):
        if not value:
            return ""
        return self._clean_text(BeautifulSoup(value, "html.parser").get_text(" ", strip=True))

    def _clean_text(self, value):
        if not value:
            return ""
        return " ".join(str(value).split()).strip()
