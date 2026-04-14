# 东帝汶gov portal爬虫，负责抓取对应站点、机构或栏目内容。

import re

from bs4 import BeautifulSoup

import scrapy

from news_scraper.spiders.timor_leste.base import TimorLesteBaseSpider


class TimorLesteGovPortalSpider(TimorLesteBaseSpider):
    name = "timor_leste_gov_portal"

    country_code = 'TLS'

    country = '东帝汶'
    allowed_domains = ["timor-leste.gov.tl"]
    target_table = "tls_gov_portal"
    start_urls = ["https://timor-leste.gov.tl/"]

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing)

    def parse_listing(self, response):
        html = self._fetch_html(self.start_urls[0])
        urls = sorted(set(re.findall(r"https://timor-leste\.gov\.tl/\?p=\d+(?:&amp;n=1)?", html)))
        for full_url in urls:
            full_url = full_url.replace("&amp;", "&")
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
            self._clean_text(" ".join(response.css(".date::text, .tit::text, body ::text").getall()[:80])),
            languages=["pt", "en"],
        )
        if publish_time and not self.full_scan and publish_time < self.cutoff_date:
            return
        content = self._extract_content(response, title)
        if not content:
            return
        yield self._build_item(
            response=response,
            title=title,
            content=content,
            publish_time=publish_time,
            author="Government of Timor-Leste",
            language="pt",
            section="government",
        )

    def _extract_content(self, response, title):
        soup = BeautifulSoup(response.text, "html.parser")
        root = soup.select_one(".post") or soup.select_one(".content") or soup.select_one("body")
        if not root:
            return ""
        for unwanted in root.select("script, style, nav, footer, header, aside, form, .slider, .sidebar"):
            unwanted.decompose()
        title_text = self._clean_text(title)
        parts = []
        for node in root.find_all(["p", "li"], recursive=True):
            text = self._clean_text(node.get_text(" ", strip=True))
            if not text or len(text) < 35 or text == title_text:
                continue
            if text.startswith("Terça-feira") or text.startswith("Sexta-feira"):
                continue
            if text not in parts:
                parts.append(text)
        return "\n\n".join(parts)
