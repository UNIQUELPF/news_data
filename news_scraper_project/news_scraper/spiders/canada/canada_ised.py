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

    async def start(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing, dont_filter=True)

    def parse_listing(self, response):
        payload = self._fetch_json(self.api_url)
        emitted = 0
        for entry in payload.get("feed", {}).get("entry", []):
            url = self._clean_text(entry.get("link"))
            title = self._clean_text(entry.get("title"))
            teaser = self._clean_text(entry.get("teaser"))
            publish_time = self._parse_datetime(entry.get("publishedDate"))
            if not url or not title:
                continue
            if not self.should_process(url, publish_time):
                continue
            if not teaser:
                continue
            # Use the API-provided data directly without fetching detail pages
            # www.canada.ca has HTTP/2 connection issues from local environment
            mock_response = self._make_response(url, f"<html><body><h1>{title}</h1><p>{teaser}</p></body></html>")
            yield self._build_item(
                mock_response, title, teaser, publish_time,
                "Innovation, Science and Economic Development Canada", "en", "government"
            )
            emitted += 1
            if emitted >= 10:
                return
