# 加拿大创新、科学与经济发展部爬虫，抓取 ISED 新闻发布。
import scrapy

from news_scraper.spiders.canada.base import CanadaBaseSpider


class CanadaIsedSpider(CanadaBaseSpider):
    name = "canada_ised"

    country_code = 'CAN'

    country = '加拿大'
    allowed_domains = []
    start_urls = ["data:,canada_ised_start"]
    api_url = (
        "https://api.io.canada.ca/io-server/gc/news/en/v2"
        "?dept=departmentofindustry&sort=publishedDate&orderBy=desc&publishedDate>=2020-08-09&pick=10"
    )

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing)

    def parse_listing(self, response):
        payload = self._fetch_json(self.api_url)
        for entry in payload.get("feed", {}).get("entry", []):
            url = self._clean_text(entry.get("link"))
            title = self._clean_text(entry.get("title"))
            teaser = self._clean_text(entry.get("teaser"))
            publish_time = self._parse_datetime(entry.get("publishedDate"))
            if not url or not title:
                continue
            if publish_time and not self.full_scan and publish_time < self.cutoff_date:
                continue
            detail_html = self._fetch_html(url)
            item = next(
                self.parse_detail(
                    self._make_response(url, detail_html),
                    fallback_title=title,
                    fallback_publish_time=publish_time,
                    fallback_teaser=teaser,
                ),
                None,
            )
            if item:
                yield item

    def parse_detail(self, response, fallback_title="", fallback_publish_time=None, fallback_teaser=""):
        title = self._clean_text(
            fallback_title
            or response.css("h1::text").get()
            or response.css("title::text").get()
        )
        if not title:
            return
        publish_time = fallback_publish_time or self._parse_datetime(
            response.xpath("//time/@datetime").get()
            or response.xpath("//meta[@name='dcterms.issued']/@content").get()
        )
        if publish_time and not self.full_scan and publish_time < self.cutoff_date:
            return
        content = self._extract_content(response, ["main"])
        if not content:
            content = fallback_teaser
        if not content:
            return
        yield self._build_item(
            response, title, content, publish_time, "Innovation, Science and Economic Development Canada", "en", "government"
        )
