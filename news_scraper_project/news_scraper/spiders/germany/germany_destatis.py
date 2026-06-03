# 德国destatis爬虫，负责抓取对应站点、机构或栏目内容。

import re

from bs4 import BeautifulSoup

import scrapy

from news_scraper.spiders.germany.base import GermanyBaseSpider


class GermanyDestatisSpider(GermanyBaseSpider):
    name = "germany_destatis"

    country_code = 'DEU'

    country = '德国'
    allowed_domains = ["destatis.de", "www.destatis.de"]
    start_urls = ["https://www.destatis.de/EN/Press/press_node.html"]

    use_curl_cffi = True
    strict_date_required = False

    async def start(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing, dont_filter=True)

    def parse_listing(self, response):
        soup = BeautifulSoup(response.text, "html.parser")
        seen = set()
        for card in soup.select(".c-result"):
            link = card.select_one(".c-result__heading a[href]")
            if not link:
                continue
            full_url = response.urljoin(link.get("href").split("?")[0])
            if full_url in seen:
                continue
            seen.add(full_url)
            date_text = self._clean_text(card.select_one(".c-result__date").get_text(" ", strip=True) if card.select_one(".c-result__date") else "")
            publish_time = self._parse_datetime(date_text, languages=["en"])
            if not self.should_process(full_url, publish_time):
                continue
            yield scrapy.Request(
                full_url,
                callback=self.parse_detail,
                meta={"publish_time": publish_time}
            )

    def parse_detail(self, response):
        title = self._clean_text(
            response.xpath("//meta[@property='og:title']/@content").get()
            or response.css("h1::text").get()
            or response.css("title::text").get()
        )
        if not title:
            return

        publish_time = response.meta.get("publish_time") or self._parse_datetime(
            self._clean_text(" ".join(response.css("body ::text").getall()[:120])),
            languages=["en"],
        )
        if not self.should_process(response.url, publish_time):
            return

        content = self._do_extract_content(response)
        if not content:
            return

        yield self._build_item(
            response=response,
            title=title,
            content=content,
            publish_time=publish_time,
            author="Destatis",
            language="en",
            section="statistics",
        )

    def _do_extract_content(self, response):
        soup = BeautifulSoup(response.text, "html.parser")
        root = soup.select_one("main") or soup.select_one(".main")
        if not root:
            return ""
        for unwanted in root.select("script, style, nav, footer, header, aside, form, .c-actions, .l-content-wrapper__headline"):
            unwanted.decompose()
        parts = []
        for node in root.find_all(["p", "li"], recursive=True):
            text = self._clean_text(node.get_text(" ", strip=True))
            if not text or len(text) < 35:
                continue
            if text.startswith("Share") or text.startswith("Back to"):
                continue
            if text not in parts:
                parts.append(text)
        return "\n\n".join(parts)

