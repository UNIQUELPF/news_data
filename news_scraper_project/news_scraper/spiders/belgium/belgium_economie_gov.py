# 比利时economie gov爬虫，使用 newsroom 站点抓取经济新闻。
# 旧站点 economie.fgov.be 有 TSPD 保护，改用 news.economie.fgov.be (pr.co 平台)。
# pr.co 平台的列表页直接包含结构化日期，无需 JS 渲染。

from bs4 import BeautifulSoup

import scrapy

from news_scraper.spiders.belgium.base import BelgiumBaseSpider


class BelgiumEconomieGovSpider(BelgiumBaseSpider):
    name = "belgium_economie_gov"

    country_code = 'BEL'

    country = '比利时'
    allowed_domains = ["news.economie.fgov.be"]
    start_urls = ["https://news.economie.fgov.be/fr/releases/"]

    fallback_content_selector = "article, main"

    async def start(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing, dont_filter=True)

    def parse_listing(self, response):
        if self._stop_pagination:
            return
        soup = BeautifulSoup(response.text, "html.parser")
        has_valid_item_in_window = False
        for item in soup.select("li.article__item"):
            href = item.select_one(".article__title a")
            if not href:
                continue
            full_url = response.urljoin(href.get("href"))
            time_tag = item.select_one("time.c-card__time")
            publish_time = None
            if time_tag:
                dt = time_tag.get("datetime")
                if dt:
                    publish_time = self._parse_datetime(dt, languages=["fr", "en"])
            if not self.should_process(full_url, publish_time):
                continue
            has_valid_item_in_window = True
            yield scrapy.Request(full_url, callback=self.parse_detail)
        if not has_valid_item_in_window:
            self._stop_pagination = True

        if not self._stop_pagination:
            next_page = response.css("a[href*='?page='][rel='next']::attr(href)").get()
            if not next_page:
                next_page = response.css("a[href*='?page=']::attr(href)").get()
            if next_page:
                yield response.follow(next_page, callback=self.parse_listing)

    def parse_detail(self, response):
        title = self._clean_text(
            response.xpath("//meta[@property='og:title']/@content").get()
            or response.css("h1::text").get()
            or response.css("title::text").get()
        )
        if not title:
            return

        publish_time = self._parse_datetime(
            response.xpath("//meta[@property='article:published_time']/@content").get()
            or response.css("time[datetime]::attr(datetime)").get(),
            languages=["fr", "en"],
        )
        if not self.should_process(response.url, publish_time):
            self._stop_pagination = True
            return

        content = self._extract_content(response, ["article", ".c-textholder", "main"])
        if not content:
            return

        yield self._build_item(
            response=response,
            title=title.strip().replace(" | FOD Economie Newsroom", "").replace(" | SPF Economie Newsroom", ""),
            content=content,
            publish_time=publish_time,
            author="FPS Economy Belgium",
            language="fr",
            section="economy",
        )
