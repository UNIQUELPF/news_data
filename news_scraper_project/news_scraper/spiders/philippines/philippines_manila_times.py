# 菲律宾manila times爬虫，负责抓取对应站点、机构或栏目内容。

import re

from bs4 import BeautifulSoup

import scrapy

from news_scraper.spiders.philippines.base import PhilippinesBaseSpider


class PhilippinesManilaTimesSpider(PhilippinesBaseSpider):
    name = "philippines_manila_times"

    country_code = 'PHL'

    country = '菲律宾'
    allowed_domains = ["manilatimes.net", "www.manilatimes.net"]
    start_urls = ["https://www.manilatimes.net/business"]

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing)

    def parse_listing(self, response):
        html = self._fetch_html(self.start_urls[0])
        urls = sorted(
            set(
                re.findall(
                    r"https://www\.manilatimes\.net/\d{4}/\d{2}/\d{2}/business/[a-z0-9\-\/]+/\d+",
                    html,
                )
            )
        )
        for full_url in urls:
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
            or response.css("time::attr(datetime), time::text").get()
            or self._clean_text(" ".join(response.css("main ::text").getall()[:80])),
            languages=["en"],
        )
        if publish_time and not self.full_scan and publish_time < self.cutoff_date:
            return

        content = self._extract_content(response, title)
        if not content:
            content = self._clean_text(response.xpath("//meta[@property='og:description']/@content").get())
        if not content:
            return

        yield self._build_item(
            response=response,
            title=title,
            content=content,
            publish_time=publish_time,
            author="The Manila Times",
            language="en",
            section="business",
        )

    def _extract_content(self, response, title):
        soup = BeautifulSoup(response.text, "html.parser")
        root = soup.select_one("article") or soup.select_one("main") or soup.select_one(".article__content")
        if not root:
            return ""
        for unwanted in root.select("script, style, nav, footer, header, aside, form, .social-share, .ad-unit"):
            unwanted.decompose()
        title_text = self._clean_text(title)
        parts = []
        for node in root.find_all(["p", "li"], recursive=True):
            text = self._clean_text(node.get_text(" ", strip=True))
            if not text or len(text) < 35 or text == title_text:
                continue
            if text.startswith("READ:") or text.startswith("TMT") or text.startswith("Subscribe"):
                continue
            if text not in parts:
                parts.append(text)
        return "\n\n".join(parts)
