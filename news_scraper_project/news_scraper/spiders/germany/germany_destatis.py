# 德国destatis爬虫，负责抓取对应站点、机构或栏目内容。

import re

from bs4 import BeautifulSoup

import scrapy

from news_scraper.spiders.germany.base import GermanyBaseSpider


class GermanyDestatisSpider(GermanyBaseSpider):
    name = "germany_destatis"
    allowed_domains = ["destatis.de", "www.destatis.de"]
    target_table = "deu_destatis"
    start_urls = ["https://www.destatis.de/EN/Press/press_node.html"]

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing)

    def parse_listing(self, response):
        html = self._fetch_html(self.start_urls[0])
        soup = BeautifulSoup(html, "html.parser")
        for card in soup.select(".c-result"):
            link = card.select_one(".c-result__heading a[href]")
            if not link:
                continue
            full_url = response.urljoin(link.get("href").split("?")[0])
            if full_url in self.seen_urls:
                continue
            date_text = self._clean_text(card.select_one(".c-result__date").get_text(" ", strip=True) if card.select_one(".c-result__date") else "")
            publish_time = self._parse_datetime(date_text, languages=["en"])
            if publish_time and not self.full_scan and publish_time < self.cutoff_date:
                continue
            self.seen_urls.add(full_url)
            try:
                detail_html = self._fetch_html(full_url)
            except Exception:
                continue
            item = next(self.parse_detail(self._make_response(full_url, detail_html), publish_time=publish_time), None)
            if item:
                yield item

    def parse_detail(self, response, publish_time=None):
        title = self._clean_text(
            response.xpath("//meta[@property='og:title']/@content").get()
            or response.css("h1::text").get()
            or response.css("title::text").get()
        )
        if not title:
            return

        final_publish_time = publish_time or self._parse_datetime(
            self._clean_text(" ".join(response.css("body ::text").getall()[:120])),
            languages=["en"],
        )
        if final_publish_time and not self.full_scan and final_publish_time < self.cutoff_date:
            return

        content = self._extract_content(response)
        if not content:
            return

        yield self._build_item(
            response=response,
            title=title,
            content=content,
            publish_time=final_publish_time,
            author="Destatis",
            language="en",
            section="statistics",
        )

    def _extract_content(self, response):
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

