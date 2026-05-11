# 阿根廷infobae爬虫，负责抓取对应站点、机构或栏目内容。

from email.utils import parsedate_to_datetime

import scrapy
from news_scraper.spiders.smart_spider import SmartSpider
from bs4 import BeautifulSoup

# 阿根廷经济类来源
# 站点：Infobae
# 入库表：arg_infobae
# 语言：西班牙语


class ArgentinaInfobaeSpider(SmartSpider):
    """阿根廷 Infobae 爬虫。

    抓取站点：https://www.infobae.com
    抓取入口：Economia RSS
    入库表：arg_infobae
    语言：西班牙语
    """

    name = "argentina_infobae"


    country_code = "ARG"


    country = "阿根廷"
    language = "en"
    source_timezone = "America/Argentina/Buenos_Aires"
    start_date = "2026-01-01"
    allowed_domains = ["infobae.com"]
    # 当前 spider 对应的数据库表名。

    # Infobae 的经济频道 RSS 稳定，适合作为增量入口。
    fallback_content_selector = "[data-testid='article-body'], article, main"

    start_urls = [
        "https://www.infobae.com/arc/outboundfeeds/rss/category/economia/",
    ]

    # 首次抓取的默认时间边界；后续优先按数据库里最新时间做增量。

    custom_settings = {
        "DOWNLOAD_DELAY": 0.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 8,
    }
    async def start(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_feed, dont_filter=True)

    def parse_feed(self, response):
        # RSS 里已经有发布时间和文章链接，适合作为稳定的列表入口。
        for item in response.xpath("//channel/item"):
            url = item.xpath("./link/text()").get()
            if not url or not self.should_process(url):
                continue
            if "/economia/" not in url:
                continue

            publish_time = self._parse_rss_datetime(item.xpath("./pubDate/text()").get())
            if publish_time and publish_time < self.cutoff_date:
                continue

            meta = {
                "rss_title": self._clean_text(item.xpath("./title/text()").get()),
                "rss_publish_time": publish_time,
                "rss_description": self._clean_html(item.xpath("./description/text()").get()),
            }
            yield scrapy.Request(url, callback=self.parse_detail, meta=meta)

    def parse_detail(self, response):
        item = self.auto_parse_item(response)
        if not item.get("title") or not item.get("content_plain"):
            # Fall back to RSS data if detail page extraction fails
            item["title"] = item.get("title") or response.meta.get("rss_title")
            item["content_plain"] = item.get("content_plain") or response.meta.get("rss_description")
            if not item.get("publish_time"):
                item["publish_time"] = response.meta.get("rss_publish_time")
            if not item.get("title") or not item.get("content_plain"):
                return

        publish_time = item.get("publish_time")
        if not self.should_process(response.url, publish_time):
            self._stop_pagination = True
            return

        # Spider-specific overrides
        item["author"] = "Infobae"
        item["section"] = "economia"
        item["language"] = "es"

        if len(item.get("content_plain", "")) > 100:
            yield item

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
