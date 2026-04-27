# 卡塔尔央行爬虫，抓取英文新闻和公告。
import scrapy

from news_scraper.spiders.qatar.base import QatarBaseSpider


class QatarQcbSpider(QatarBaseSpider):
    name = "qatar_qcb"

    country_code = 'QAT'

    allowed_domains = []
    start_urls = ["https://www.qcb.gov.qa/en/News/Pages/default.aspx"]

    def start_requests(self):
        for suffix in ["10apr2.aspx", "september4.aspx", "6jan1.aspx", "16march1.aspx", "january2.aspx", "11july1.aspx"]:
            url = f"https://www.qcb.gov.qa/en/News/Pages/{suffix}"
            if not self.should_process(url):
                continue
            yield scrapy.Request(url, callback=self.parse_detail)

    def parse_detail(self, response):
        if "error.aspx" in response.url.lower():
            return

        title = self._clean_text(
            response.css("h1::text").get()
            or response.css("title::text").get()
        )
        if not title or title.lower() == "error":
            return

        raw_date = self._clean_text(
            response.css(".news-details *::text").get()
            or response.css("title::text").get()
        )
        publish_time = self._parse_datetime(raw_date, languages=["en"])
        if not self.should_process(response.url, publish_time):
            return

        content = self._clean_text(" ".join(response.css("title::text, h1::text, .news-details *::text").getall()))
        if not content:
            return

        yield self._build_item(
            response=response,
            title=title,
            content=content,
            publish_time=publish_time,
            author="Qatar Central Bank",
            language="en",
            section="central-bank",
        )
