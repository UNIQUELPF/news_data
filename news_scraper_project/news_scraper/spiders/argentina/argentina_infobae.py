# 阿根廷infobae爬虫，负责抓取对应站点、机构或栏目内容。

from datetime import datetime
from email.utils import parsedate_to_datetime

import scrapy
from news_scraper.spiders.smart_spider import SmartSpider
from bs4 import BeautifulSoup
from news_scraper.items import NewsItem

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
    start_urls = [
        "https://www.infobae.com/arc/outboundfeeds/rss/category/economia/",
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
        # RSS 里已经有发布时间和文章链接，适合作为稳定的列表入口。
        for item in response.xpath("//channel/item"):
            url = item.xpath("./link/text()").get()
            if not url or not self.should_process(url):
                continue
            if "/economia/" not in url:
                continue

            publish_time = self._parse_rss_datetime(item.xpath("./pubDate/text()").get())
            if publish_time and not self.full_scan and publish_time < self.cutoff_date:
                continue

            meta = {
                "rss_title": self._clean_text(item.xpath("./title/text()").get()),
                "rss_publish_time": publish_time,
                "rss_description": self._clean_html(item.xpath("./description/text()").get()),
            }
            yield scrapy.Request(url, callback=self.parse_detail, meta=meta)

    def parse_detail(self, response):
        # 详情页优先取 articleBody 和正文段落，避免只存 RSS 摘要。
        title = self._clean_text(
            response.xpath("//meta[@property='og:title']/@content").get()
            or response.css("h1::text").get()
            or response.meta.get("rss_title")
        )
        if not title:
            return

        publish_time = self._parse_iso_datetime(
            response.xpath("//meta[@property='article:published_time']/@content").get()
        ) or response.meta.get("rss_publish_time")

        if publish_time and not self.full_scan and publish_time < self.cutoff_date:
            return

        content = self._extract_content(response)
        if not content:
            content = response.meta.get("rss_description", "")
        if not content:
            return

        author = self._clean_text(
            response.xpath("//meta[@name='author']/@content").get()
            or response.xpath("//meta[@property='article:author']/@content").get()
        ) or "Infobae"

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
        root = (
            soup.select_one("[data-testid='article-body']")
            or soup.select_one("article")
            or soup.select_one("main")
        )
        if not root:
            return ""

        for unwanted in root.select(
            "script, style, nav, footer, header, aside, form, figure, .share, .related, .newsletter"
        ):
            unwanted.decompose()

        parts = []
        for node in root.find_all(["p", "h2", "h3", "li"], recursive=True):
            text = self._clean_text(node.get_text(" ", strip=True))
            if not text or len(text) < 30:
                continue
            if text not in parts:
                parts.append(text)

        return "\n\n".join(parts)

    def _parse_rss_datetime(self, value):
        if not value:
            return None
        try:
            return parsedate_to_datetime(value).replace(tzinfo=None)
        except Exception:
            return None

    def _parse_iso_datetime(self, value):
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
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
