# 比利时belgium portal爬虫，负责抓取对应站点、机构或栏目内容。

from bs4 import BeautifulSoup

import scrapy

from news_scraper.spiders.belgium.base import BelgiumBaseSpider


class BelgiumPortalSpider(BelgiumBaseSpider):
    name = "belgium_belgium_portal"

    country_code = 'BEL'

    country = '比利时'
    allowed_domains = ["belgium.be", "www.belgium.be"]
    target_table = "bel_belgium_portal"
    start_urls = ["https://www.belgium.be/en/News/overview?f%5B0%5D=theme%3A56"]
    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing)

    def parse_listing(self, response):
        html = self._fetch_html(self.start_urls[0])
        soup = BeautifulSoup(html, "html.parser")
        for link in soup.select("a[href]"):
            href = link.get("href")
            if not href or "/en/news/" not in href or href.endswith("/overview"):
                continue
            full_url = response.urljoin(href)
            if full_url in self.seen_urls or full_url.endswith("/overview"):
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
            or response.css("title::text").get()
            or response.css("h1::text").get()
        )
        if not title:
            return

        node_text = self._clean_text(" ".join(response.css(".node ::text, main ::text").getall()[:120]))
        publish_time = self._parse_datetime(node_text, languages=["en"])
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
            author="Belgium.be",
            language="en",
            section="economy",
        )

    def _extract_content(self, response):
        soup = BeautifulSoup(response.text, "html.parser")
        root = soup.select_one(".field--name-body") or soup.select_one(".node") or soup.select_one("main")
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
