# 法国latribune爬虫，负责抓取对应站点、机构或栏目内容。

import re

from bs4 import BeautifulSoup

import scrapy

from news_scraper.spiders.france.base import FranceBaseSpider


class FranceLaTribuneSpider(FranceBaseSpider):
    name = "france_latribune"

    country_code = 'FRA'

    country = '法国'
    allowed_domains = ["latribune.fr", "www.latribune.fr"]
    start_urls = ["https://www.latribune.fr/economie-2/"]

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing)

    def parse_listing(self, response):
        html = self._fetch_html(self.start_urls[0])
        urls = sorted(set(re.findall(r'/article/economie(?:/[a-z0-9\-]+)*/\d+/[a-z0-9\-]+', html)))
        for href in urls:
            full_url = response.urljoin(href)
            if not self.should_process(full_url):
                continue
            try:
                detail_html = self._fetch_html(full_url)
            except Exception:
                continue
            item = next(self.parse_detail(self._make_response(full_url, detail_html)), None)
            if item:
                yield item

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
            or response.xpath("//meta[@name='date']/@content").get()
            or self._clean_text(" ".join(response.css("main ::text").getall()[:120])),
            languages=["fr", "en"],
        )
        if publish_time and not self.full_scan and publish_time < self.cutoff_date:
            return

        content = self._extract_content(response, title)
        if not content:
            content = self._clean_text(response.xpath("//meta[@name='description']/@content").get())
        if not content:
            return

        yield self._build_item(
            response=response,
            title=title,
            content=content,
            publish_time=publish_time,
            author="La Tribune",
            language="fr",
            section="economy",
        )

    def _extract_content(self, response, title):
        soup = BeautifulSoup(response.text, "html.parser")
        root = soup.select_one("main") or soup.select_one("article")
        if not root:
            return ""
        for unwanted in root.select("script, style, nav, footer, header, aside, form"):
            unwanted.decompose()
        title_text = self._clean_text(title)
        parts = []
        for node in root.find_all(["p", "li"], recursive=True):
            text = self._clean_text(node.get_text(" ", strip=True))
            if not text or len(text) < 35 or text == title_text:
                continue
            if text.startswith("Partager") or text.startswith("Votre email"):
                continue
            if text not in parts:
                parts.append(text)
        return "\n\n".join(parts)
