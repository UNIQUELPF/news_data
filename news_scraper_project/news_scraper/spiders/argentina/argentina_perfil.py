# 阿根廷perfil爬虫，负责抓取对应站点、机构或栏目内容。

from datetime import datetime

import dateparser
import scrapy
from news_scraper.spiders.smart_spider import SmartSpider
from bs4 import BeautifulSoup
from news_scraper.items import NewsItem

# 阿根廷经济类来源
# 站点：Perfil
# 入库表：arg_perfil
# 语言：西班牙语


class ArgentinaPerfilSpider(SmartSpider):
    """阿根廷 Perfil 爬虫。

    抓取站点：https://www.perfil.com
    抓取栏目：economia
    入库表：arg_perfil
    语言：西班牙语
    """

    name = "argentina_perfil"


    country_code = "ARG"


    country = "阿根廷"
    language = "en"
    source_timezone = "America/Argentina/Buenos_Aires"
    start_date = "2026-01-01"
    allowed_domains = ["perfil.com"]
    # 当前 spider 对应的数据库表名。

    # 从经济栏目入口页开始抓取。
    start_urls = [
        "https://www.perfil.com/seccion/economia",
    ]

    # 首次抓取的默认时间边界；后续优先按数据库里最新时间做增量。

    custom_settings = {
        "DOWNLOAD_DELAY": 0.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 8,
    }


    @classmethod


    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing)

    def parse_listing(self, response):
        # Perfil 栏目页直接筛经济文章详情链接。
        article_links = response.css('a[href*="/noticias/economia/"]::attr(href)').getall()

        for href in article_links:
            full_url = response.urljoin(href)
            if not self.should_process(full_url):
                continue
            yield scrapy.Request(full_url, callback=self.parse_detail)

    def parse_detail(self, response):
        # 详情页从 article 容器抽正文，兼容 Perfil 的常见页面结构。
        title = self._clean_text(response.css("h1::text").get())
        if not title:
            title = self._clean_text(response.xpath("//meta[@property='og:title']/@content").get())
        if not title:
            return

        publish_time = self._parse_datetime(response.xpath("//meta[@property='article:published_time']/@content").get())
        if publish_time and not self.full_scan and publish_time < self.cutoff_date:
            return

        soup = BeautifulSoup(response.text, "html.parser")
        root = soup.select_one("article")
        if not root:
            return

        for unwanted in root.select("script, style, nav, footer, header, aside, form, figure"):
            unwanted.decompose()

        parts = []
        for node in root.find_all(["p", "h2", "h3", "li"], recursive=True):
            text = self._clean_text(node.get_text(" ", strip=True))
            if not text or len(text) < 30:
                continue
            if text not in parts:
                parts.append(text)

        content = "\n\n".join(parts) if parts else self._clean_text(response.xpath("//meta[@property='og:description']/@content").get())
        if not content:
            return

        author = self._clean_text(response.xpath("//*[contains(@class, 'author')]/text()").get()) or "Perfil"

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
