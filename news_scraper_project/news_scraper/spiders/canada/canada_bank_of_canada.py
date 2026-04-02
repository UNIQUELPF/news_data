# 加拿大央行爬虫，抓取公告与新闻发布。
from bs4 import BeautifulSoup
import scrapy

from news_scraper.spiders.canada.base import CanadaBaseSpider


class CanadaBankOfCanadaSpider(CanadaBaseSpider):
    name = "canada_bank_of_canada"
    allowed_domains = []
    target_table = "can_bank_of_canada"
    start_urls = ["data:,canada_bank_of_canada_start"]
    list_url = "https://www.bankofcanada.ca/press/announcements/"

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing)

    def parse_listing(self, response):
        html = self._fetch_html(self.list_url)
        soup = BeautifulSoup(html, "html.parser")
        emitted = 0
        for link in soup.select("main a[href], article a[href]"):
            url = self._clean_text(link.get("href"))
            title = self._clean_text(link.get_text(" ", strip=True))
            if url.startswith("/"):
                url = response.urljoin(url)
            if not url or not title:
                continue
            if not url.startswith("https://www.bankofcanada.ca/20"):
                continue
            if url in self.seen_urls:
                continue
            self.seen_urls.add(url)
            detail_html = self._fetch_html(url)
            item_obj = next(
                self.parse_detail(
                    self._make_response(url, detail_html),
                    fallback_title=title,
                ),
                None,
            )
            if item_obj:
                yield item_obj
                emitted += 1
                if emitted >= 10:
                    return

    def parse_detail(self, response, fallback_title="", fallback_publish_time=None):
        title = self._clean_text(
            fallback_title
            or response.xpath("//meta[@property='og:title']/@content").get()
            or response.css("h1::text").get()
            or response.css("title::text").get()
        )
        if not title:
            return
        publish_time = fallback_publish_time or self._parse_datetime(
            response.xpath("//time/@datetime").get()
            or response.xpath("//meta[@property='article:published_time']/@content").get()
            or response.xpath("//meta[@name='publication_date']/@content").get()
        )
        if publish_time and not self.full_scan and publish_time < self.cutoff_date:
            return
        content = self._extract_content(response, ["main", "article"])
        if not content:
            content = self._clean_text(response.xpath("//meta[@name='description']/@content").get())
        if not content:
            return
        yield self._build_item(response, title, content, publish_time, "Bank of Canada", "en", "central-bank")
