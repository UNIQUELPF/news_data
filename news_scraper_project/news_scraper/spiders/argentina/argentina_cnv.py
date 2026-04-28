# 阿根廷cnv爬虫，负责抓取对应站点、机构或栏目内容。

from datetime import datetime

import dateparser
import scrapy
from news_scraper.spiders.smart_spider import SmartSpider
from bs4 import BeautifulSoup
from news_scraper.items import NewsItem

# 阿根廷政府/监管类来源
# 站点：CNV
# 入库表：arg_cnv
# 语言：西班牙语


class ArgentinaCnvSpider(SmartSpider):
    """阿根廷国家证券委员会 CNV 爬虫。

    抓取站点：https://www.argentina.gob.ar/cnv
    抓取栏目：noticias
    入库表：arg_cnv
    语言：西班牙语
    """

    name = "argentina_cnv"


    country_code = "ARG"


    country = "阿根廷"
    language = "en"
    source_timezone = "America/Argentina/Buenos_Aires"
    start_date = "2026-01-01"
    allowed_domains = ["argentina.gob.ar"]

    start_urls = [
        "https://www.argentina.gob.ar/cnv/noticias",
    ]

    custom_settings = {
        "DOWNLOAD_DELAY": 0.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 8,
    }


    @classmethod


    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing)

    def parse_listing(self, response):
        article_links = response.css('a[href*="/noticias/"]::attr(href)').getall()

        for href in article_links:
            full_url = response.urljoin(href)
            if "/noticias/" not in full_url or not self.should_process(full_url):
                continue
            yield scrapy.Request(full_url, callback=self.parse_detail)

        if self.reached_cutoff:
            return

        next_page = response.css("li.pager__item--next a::attr(href), a[rel='next']::attr(href)").get()
        if next_page:
            yield response.follow(next_page, callback=self.parse_listing)

    def parse_detail(self, response):
        title = self._clean_text(
            response.xpath("//meta[@property='og:title']/@content").get()
            or response.xpath("//meta[@name='twitter:title']/@content").get()
        )
        if not title:
            return

        publish_time = self._parse_datetime(
            response.xpath("//meta[@property='article:published_time']/@content").get()
            or response.css("time::attr(datetime), time::text").get()
        )
        if publish_time and not self.full_scan and publish_time < self.cutoff_date:
            self.reached_cutoff = True
            return

        content = self._extract_content(response)
        if not content:
            content = self._clean_text(
                response.xpath("//meta[@property='og:description']/@content").get()
                or response.xpath("//meta[@name='description']/@content").get()
            )
        if not content:
            return

        item = NewsItem()
        item["url"] = response.url
        item["title"] = title
        item["content"] = content
        item["publish_time"] = publish_time or datetime.now()
        item["author"] = "CNV"
        item["language"] = "es"
        item["section"] = "noticias"
        item["scrape_time"] = datetime.now()
        yield item

    def _extract_content(self, response):
        soup = BeautifulSoup(response.text, "html.parser")
        root = soup.select_one("article") or soup.select_one("main")
        if not root:
            return ""

        for unwanted in root.select("script, style, nav, footer, header, aside, form, .share, .social"):
            unwanted.decompose()

        parts = []
        for node in root.find_all(["p", "h2", "h3", "li"], recursive=True):
            text = self._clean_text(node.get_text(" ", strip=True))
            if not text or len(text) < 12:
                continue
            if text in ("Compartir en Facebook", "Compartir en X", "Compartir en Linkedin", "Compartir en Whatsapp"):
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
