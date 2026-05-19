# 阿尔及利亚cosob爬虫，负责抓取对应站点、机构或栏目内容。

import io
from datetime import datetime

import dateparser
import scrapy
from news_scraper.spiders.smart_spider import SmartSpider
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
    allowed_domains = ["cosob.dz"]

    fallback_content_selector = ".entry-content, article"

    start_urls = [
        "https://cosob.dz/category/actualites/",
    ]

    custom_settings = {
        "DOWNLOAD_DELAY": 0.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 8,
    }
    async def start(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing, dont_filter=True)

    def parse_listing(self, response):
        article_links = response.css("article a[href], .rtin-item a[href], .entry-title a[href]")

        has_valid_item_in_window = False
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
            has_valid_item_in_window = True
            if full_url.lower().endswith(".pdf"):
                yield scrapy.Request(full_url, callback=self.parse_pdf, cb_kwargs={"title": title}, dont_filter=self.full_scan)
                continue
            yield scrapy.Request(full_url, callback=self.parse_detail, dont_filter=self.full_scan)

        if self._stop_pagination:
            return

        if has_valid_item_in_window:
            next_page = response.css("a.next.page-numbers::attr(href), a[rel='next']::attr(href)").get()
            if next_page:
                yield response.follow(next_page, callback=self.parse_listing)

    def parse_detail(self, response):
        if not isinstance(response, scrapy.http.TextResponse):
            return

        item = self.auto_parse_item(response)
        if not item.get("title") or not item.get("content_plain"):
            return

        publish_time = item.get("publish_time")
        if not self.should_process(response.url, publish_time):
            self._stop_pagination = True
            return

        # Spider-specific overrides
        item["author"] = "COSOB"
        item["section"] = "actualites"
        item["language"] = "fr"

        if len(item.get("content_plain", "")) > 100:
            yield item

    def parse_pdf(self, response, title):
        content = self._extract_pdf_text(response.body)
        if not content:
            content = title

        publish_time = self._parse_datetime(title) or self._parse_datetime(response.url)
        if publish_time and publish_time < self.cutoff_date:
            self._stop_pagination = True
            return

        item = {
            "url": response.url,
            "title": title,
            "content": content,
            "content_plain": content,
            "publish_time": publish_time or datetime.now(),
            "author": "COSOB",
            "language": "fr",
            "section": "actualites",
            "scrape_time": datetime.now(),
        }
        yield item

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
