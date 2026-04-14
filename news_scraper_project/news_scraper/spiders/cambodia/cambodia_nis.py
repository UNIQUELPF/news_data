# 柬埔寨国家统计局爬虫，抓取 NIS 英文 RSS 和统计发布内容。
from bs4 import BeautifulSoup
import scrapy

from news_scraper.spiders.cambodia.base import CambodiaBaseSpider


class CambodiaNisSpider(CambodiaBaseSpider):
    name = "cambodia_nis"

    country_code = 'KHM'

    country = '柬埔寨'
    allowed_domains = []
    target_table = "khm_nis"
    start_urls = ["data:,cambodia_nis_start"]
    feed_url = "https://www.nis.gov.kh/en/feed/"

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing)

    def parse_listing(self, response):
        xml = self._fetch_html(self.feed_url)
        soup = BeautifulSoup(xml, "xml")
        emitted = 0
        for entry in soup.find_all("item"):
            url = self._clean_text(entry.find("link").get_text()) if entry.find("link") else ""
            title = self._clean_text(entry.find("title").get_text()) if entry.find("title") else ""
            description = self._clean_text(entry.find("content:encoded").get_text()) if entry.find("content:encoded") else ""
            publish_time = self._parse_datetime(
                self._clean_text(entry.find("pubDate").get_text()) if entry.find("pubDate") else "",
                languages=["en"],
            )
            if not url or not title:
                continue
            if publish_time and not self.full_scan and publish_time < self.cutoff_date:
                continue
            if url in self.seen_urls:
                continue
            self.seen_urls.add(url)
            detail_html = self._fetch_html(url)
            item = next(
                self.parse_detail(
                    self._make_response(url, detail_html),
                    fallback_title=title,
                    fallback_publish_time=publish_time,
                    fallback_content=description,
                ),
                None,
            )
            if item:
                yield item
                emitted += 1
                if emitted >= 12:
                    return

    def parse_detail(self, response, fallback_title="", fallback_publish_time=None, fallback_content=""):
        title = self._clean_text(
            fallback_title
            or response.css("title::text").get()
            or response.xpath("//meta[@property='og:title']/@content").get()
        )
        if not title:
            return
        publish_time = fallback_publish_time
        if publish_time and not self.full_scan and publish_time < self.cutoff_date:
            return
        content = self._extract_content(response, ["main", ".site-content", "body"])
        if not content:
            content = fallback_content
        if not content:
            return
        yield self._build_item(response, title, content, publish_time, "NIS Cambodia", "en", "statistics")
