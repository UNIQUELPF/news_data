# 丹麦nationalbank爬虫，负责抓取对应站点、机构或栏目内容。

from bs4 import BeautifulSoup

import scrapy

from news_scraper.spiders.denmark.base import DenmarkBaseSpider


class DenmarkNationalbankSpider(DenmarkBaseSpider):
    name = "denmark_nationalbank"
    allowed_domains = ["nationalbanken.dk", "www.nationalbanken.dk"]
    target_table = "dnk_nationalbank"
    start_urls = ["https://www.nationalbanken.dk/en/news-and-knowledge/publications-and-speeches/"]

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing)

    def parse_listing(self, response):
        html = self._fetch_html(self.start_urls[0])
        soup = BeautifulSoup(html, "html.parser")
        for link in soup.select("a[href]"):
            href = link.get("href")
            if not href or "/en/news-and-knowledge/publications-and-speeches/" not in href:
                continue
            if any(part in href for part in ("/archive-speeches/", "/podcasts")):
                continue
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
            or response.css("title::text").get()
            or response.css("h1::text").get()
        )
        if not title:
            return

        main_text = self._clean_text(" ".join(response.css("main ::text").getall()[:160]))
        publish_time = self._parse_datetime(main_text, languages=["en"])
        if publish_time and not self.full_scan and publish_time < self.cutoff_date:
            return

        content = self._extract_content(response)
        if not content:
            return

        section = "analysis" if "/analysis/" in response.url else "speech"
        yield self._build_item(
            response=response,
            title=title,
            content=content,
            publish_time=publish_time,
            author="Danmarks Nationalbank",
            language="en",
            section=section,
        )

    def _extract_content(self, response):
        soup = BeautifulSoup(response.text, "html.parser")
        root = soup.select_one("main")
        if not root:
            return ""
        for unwanted in root.select("script, style, nav, footer, header, aside, form"):
            unwanted.decompose()
        parts = []
        for node in root.find_all(["p", "li"], recursive=True):
            text = self._clean_text(node.get_text(" ", strip=True))
            if not text or len(text) < 40:
                continue
            if text.startswith("Analyses focus on current issues"):
                continue
            if text not in parts:
                parts.append(text)
        return "\n\n".join(parts)
