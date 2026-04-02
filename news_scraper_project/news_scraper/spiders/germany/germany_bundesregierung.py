# 德国bundesregierung爬虫，负责抓取对应站点、机构或栏目内容。

import re

from bs4 import BeautifulSoup

import scrapy

from news_scraper.spiders.germany.base import GermanyBaseSpider


class GermanyBundesregierungSpider(GermanyBaseSpider):
    name = "germany_bundesregierung"
    allowed_domains = ["bundesregierung.de", "www.bundesregierung.de"]
    target_table = "deu_bundesregierung"
    start_urls = ["https://www.bundesregierung.de/breg-en/news"]

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing)

    def parse_listing(self, response):
        html = self._fetch_html(self.start_urls[0])
        for href in sorted(set(re.findall(r"/breg-en/news/[A-Za-z0-9-]+-\d+", html))):
            full_url = response.urljoin(href)
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

    def parse_detail(self, response):
        title = self._clean_text(
            response.xpath("//meta[@property='og:title']/@content").get()
            or response.css("h1::text").get()
            or response.css("title::text").get()
        )
        if not title:
            return

        publish_time = self._parse_datetime(
            self._clean_text(
                response.xpath("//time/@datetime").get()
                or " ".join(response.css("body ::text").getall()[:120])
            ),
            languages=["de", "en"],
        )
        if publish_time and not self.full_scan and publish_time < self.cutoff_date:
            return

        content = self._extract_content(response)
        if not content:
            return

        yield self._build_item(
            response=response,
            title=title,
            content=content,
            publish_time=publish_time,
            author="Federal Government",
            language="en",
            section="government",
        )

    def _extract_content(self, response):
        soup = BeautifulSoup(response.text, "html.parser")
        for unwanted in soup.select(".bpa-cookie-banner, .bpa-tools, script, style, nav, footer, header, aside, form"):
            unwanted.decompose()
        candidates = soup.select("main .bpa-article .bpa-richtext, .bpa-article .bpa-richtext")
        root = max(candidates, key=lambda node: len(node.get_text(" ", strip=True)), default=None)
        if not root:
            root = soup.select_one(".bpa-article") or soup.select_one("main")
        if not root:
            return ""
        for unwanted in root.select("script, style, nav, footer, header, aside, form, .bpa-tools, figure, .hinweis"):
            unwanted.decompose()
        parts = []
        for node in root.find_all(["p", "li"], recursive=True):
            text = self._clean_text(node.get_text(" ", strip=True))
            if not text or len(text) < 35:
                continue
            if text.startswith("Data privacy information") or text.startswith("Select all") or text.startswith("Confirm selection"):
                continue
            if text not in parts:
                parts.append(text)
        return "\n\n".join(parts)
