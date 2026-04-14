# 吉尔吉斯斯坦政府英文新闻爬虫，抓取内阁门户新闻与新闻发布。

import re

import scrapy

from news_scraper.spiders.kyrgyzstan.base import KyrgyzstanBaseSpider


class KyrgyzstanGovSpider(KyrgyzstanBaseSpider):
    name = "kyrgyzstan_gov"

    country_code = 'KGZ'

    country = '吉尔吉斯斯坦'
    allowed_domains = []
    target_table = "kgz_gov"
    start_urls = ["data:,kyrgyzstan_gov_start"]
    source_urls = [
        "https://www.gov.kg/en/post/all",
        "https://www.gov.kg/en/post/c/press",
    ]

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing)

    def parse_listing(self, response):
        emitted = 0
        for source_url in self.source_urls:
            html = self._fetch_html(source_url)
            for href in re.findall(r'https://www\.gov\.kg/en/post/s/[^"\']+', html):
                full_url = href.split("?")[0]
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
        title = re.sub(r"\s*\|\s*Кыргыз Республикасынын Министрлер Кабинети$", "", title).strip()
        if not title:
            return

        publish_time = self._parse_datetime(
            self._extract_first_match(response.text, r"(\d{1,2}\s+[A-Za-zА-Яа-яЁё]+\s+\d{4})"),
            languages=["en", "ru"],
        )
        if publish_time and not self.full_scan and publish_time < self.cutoff_date:
            return

        content = self._extract_content(response, ["main"])
        if not content:
            content = self._clean_text(response.xpath("//meta[@name='description']/@content").get())
        if not content:
            return

        yield self._build_item(
            response=response,
            title=title,
            content=content,
            publish_time=publish_time,
            author="Cabinet of Ministers of the Kyrgyz Republic",
            language="en",
            section="government",
        )

    def _extract_first_match(self, text, pattern):
        match = re.search(pattern, text)
        return match.group(1) if match else ""
