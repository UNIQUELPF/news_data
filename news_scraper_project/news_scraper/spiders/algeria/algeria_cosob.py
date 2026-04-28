# 阿尔及利亚cosob爬虫，负责抓取对应站点、机构或栏目内容。

import io
from datetime import datetime

import dateparser
import scrapy
from news_scraper.spiders.smart_spider import SmartSpider
from bs4 import BeautifulSoup
from news_scraper.items import NewsItem
from pypdf import PdfReader

# 阿尔及利亚政府/监管类来源
# 站点：COSOB
# 入库表：dza_cosob
# 语言：法语


class AlgeriaCosobSpider(SmartSpider):
    """阿尔及利亚证券监管机构 COSOB 爬虫。 政府/官方监管机构

    抓取站点：https://cosob.dz
    抓取栏目：Actualités
    入库表：dza_cosob
    语言：法语
    """

    name = "algeria_cosob"


    country_code = "DZA"


    country = "阿尔及利亚"
    language = "en"
    source_timezone = "Africa/Algiers"
    start_date = "2026-01-01"
    allowed_domains = ["cosob.dz"]

    start_urls = [
        "https://cosob.dz/category/actualites/",
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
        article_links = response.css("article a[href], .rtin-item a[href], .entry-title a[href]")

        for link in article_links:
            href = link.attrib.get("href")
            if not href:
                continue
            full_url = response.urljoin(href)
            title = self._clean_text(link.xpath("normalize-space()").get()) or full_url.rsplit("/", 1)[-1]
            if (
                not self.should_process(full_url)
                or "/category/" in full_url
                or "/author/" in full_url
            ):
                continue
            if full_url.lower().endswith(".pdf"):
                yield scrapy.Request(full_url, callback=self.parse_pdf, cb_kwargs={"title": title})
                continue
            yield scrapy.Request(full_url, callback=self.parse_detail)

        if self.reached_cutoff:
            return

        next_page = response.css("a.next.page-numbers::attr(href), a[rel='next']::attr(href)").get()
        if next_page:
            yield response.follow(next_page, callback=self.parse_listing)

    def parse_detail(self, response):
        if not isinstance(response, scrapy.http.TextResponse):
            return

        title = self._clean_text(response.css("h1::text").get() or response.xpath("//meta[@property='og:title']/@content").get())
        if not title:
            return

        publish_time = self._extract_publish_time(response)
        if publish_time and not self.full_scan and publish_time < self.cutoff_date:
            self.reached_cutoff = True
            return

        content = self._extract_content(response, title)
        if not content:
            return

        item = NewsItem()
        item["url"] = response.url
        item["title"] = title
        item["content"] = content
        item["publish_time"] = publish_time or datetime.now()
        item["author"] = "COSOB"
        item["language"] = "fr"
        item["section"] = "actualites"
        item["scrape_time"] = datetime.now()
        yield item

    def parse_pdf(self, response, title):
        content = self._extract_pdf_text(response.body)
        if not content:
            content = title

        publish_time = self._parse_datetime(title) or self._parse_datetime(response.url)
        if publish_time and not self.full_scan and publish_time < self.cutoff_date:
            self.reached_cutoff = True
            return

        item = NewsItem()
        item["url"] = response.url
        item["title"] = title
        item["content"] = content
        item["publish_time"] = publish_time or datetime.now()
        item["author"] = "COSOB"
        item["language"] = "fr"
        item["section"] = "actualites"
        item["scrape_time"] = datetime.now()
        yield item

    def _extract_publish_time(self, response):
        value = response.xpath("//meta[@property='article:published_time']/@content").get()
        if not value:
            value = self._clean_text(" ".join(response.css("article ::text").getall()[:40]))
        return self._parse_datetime(value)

    def _extract_content(self, response, title):
        soup = BeautifulSoup(response.text, "html.parser")
        root = soup.select_one(".entry-content") or soup.select_one("article")
        if not root:
            return ""

        for unwanted in root.select("script, style, nav, footer, header, aside, form, figure, .share"):
            unwanted.decompose()

        parts = []
        for node in root.find_all(["p", "h2", "h3", "li"], recursive=True):
            text = self._clean_text(node.get_text(" ", strip=True))
            if not text or len(text) < 12:
                continue
            if text == title:
                continue
            if text not in parts:
                parts.append(text)
        return "\n\n".join(parts)

    def _parse_datetime(self, value):
        if not value:
            return None
        parsed = dateparser.parse(value, languages=["fr"], settings={"TIMEZONE": "UTC"})
        if not parsed:
            return None
        return parsed.replace(tzinfo=None)

    def _clean_text(self, value):
        if not value:
            return ""
        return " ".join(str(value).replace("\x00", " ").split()).strip()

    def _extract_pdf_text(self, pdf_bytes, max_pages=4):
        if not pdf_bytes:
            return ""

        try:
            reader = PdfReader(io.BytesIO(pdf_bytes))
        except Exception as exc:
            self.logger.warning(f"PDF parse failed for {self.name}: {exc}")
            return ""

        parts = []
        total_pages = min(len(reader.pages), max_pages)
        for page in reader.pages[:total_pages]:
            try:
                text = self._clean_text(page.extract_text() or "")
            except Exception:
                text = ""
            if text:
                parts.append(text)

        return "\n\n".join(parts)
