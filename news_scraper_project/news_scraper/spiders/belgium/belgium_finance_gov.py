# 比利时finance gov爬虫，负责抓取对应站点、机构或栏目内容。

from bs4 import BeautifulSoup

import scrapy

from news_scraper.spiders.belgium.base import BelgiumBaseSpider


class BelgiumFinanceGovSpider(BelgiumBaseSpider):
    name = "belgium_finance_gov"

    country_code = 'BEL'

    country = '比利时'
    allowed_domains = ["finance.belgium.be", "financien.belgium.be"]
    start_urls = ["https://finance.belgium.be/en/news"]

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing)

    def parse_listing(self, response):
        html = self._fetch_html(self.start_urls[0])
        soup = BeautifulSoup(html, "html.parser")
        for link in soup.select("a[href]"):
            href = link.get("href")
            if not href or "/en/news/" not in href:
                continue
            full_url = response.urljoin(href)
            if full_url.rstrip("/") == self.start_urls[0].rstrip("/") or not self.should_process(full_url):
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
            or response.css("title::text").get()
            or response.css("h1:last-of-type::text, h1::text").get()
            or response.xpath("//meta[@property='og:title']/@content").get()
        )
        if not title or title == "FPS Finance":
            return

        article_text = self._clean_text(" ".join(response.css("article ::text, main ::text").getall()[:160]))
        publish_time = self._parse_datetime(article_text, languages=["en"])
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
            author="FPS Finance",
            language="en",
            section="finance",
        )

    def _extract_content(self, response):
        soup = BeautifulSoup(response.text, "html.parser")
        root = (
            soup.select_one(".field-name-body")
            or soup.select_one("article")
            or soup.select_one(".region-content")
            or soup.select_one("main")
        )
        if not root:
            return ""
        for unwanted in root.select("script, style, nav, footer, header, aside, form"):
            unwanted.decompose()
        parts = []
        for node in root.find_all(["p", "li"], recursive=True):
            text = self._clean_text(node.get_text(" ", strip=True))
            if not text or len(text) < 25 or text.startswith("Date:"):
                continue
            if text not in parts:
                parts.append(text)
        return "\n\n".join(parts)
