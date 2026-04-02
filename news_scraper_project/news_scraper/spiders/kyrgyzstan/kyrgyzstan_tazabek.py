# 吉尔吉斯斯坦 Tazabek 财经新闻爬虫，抓取站点首页的经济与投资文章。

import re

import scrapy

from news_scraper.spiders.kyrgyzstan.base import KyrgyzstanBaseSpider


class KyrgyzstanTazabekSpider(KyrgyzstanBaseSpider):
    name = "kyrgyzstan_tazabek"
    allowed_domains = []
    target_table = "kgz_tazabek"
    start_urls = ["data:,kyrgyzstan_tazabek_start"]
    source_url = "https://www.tazabek.kg/"

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing)

    def parse_listing(self, response):
        html = self._fetch_html(self.source_url)
        emitted = 0
        for href in re.findall(r'href="(/news:\d+[^"]*)"', html):
            full_url = "https://www.tazabek.kg" + href.split("?")[0]
            if full_url in self.seen_urls:
                continue
            self.seen_urls.add(full_url)
            try:
                detail_html = self._fetch_html(full_url)
            except Exception:
                continue
            item = next(self.parse_detail(self._make_response(full_url, detail_html)), None)
            if item:
                yield item
                emitted += 1
                if emitted >= 12:
                    return

    def parse_detail(self, response):
        title = self._clean_text(
            response.xpath("//meta[@property='og:title']/@content").get()
            or response.css("title::text").get()
        )
        title = re.sub(r"\s*—\s*Tazabek$", "", title).strip()
        if not title:
            return

        publish_time = self._parse_datetime(
            response.xpath("//meta[@property='article:published_time']/@content").get()
            or self._extract_first_match(response.text, r"(\d{2}:\d{2},\s*\d{1,2}\s+[^\s]+\s+\d{4})"),
            languages=["ru"],
        )
        if publish_time and not self.full_scan and publish_time < self.cutoff_date:
            return

        content = self._extract_content(response, [".content", "main", "article"])
        if not content:
            content = self._clean_text(response.xpath("//meta[@name='description']/@content").get())
        if not content:
            return

        yield self._build_item(
            response=response,
            title=title,
            content=content,
            publish_time=publish_time,
            author="Tazabek",
            language="ru",
            section="economy",
        )

    def _extract_first_match(self, text, pattern):
        match = re.search(pattern, text)
        return match.group(1) if match else ""
