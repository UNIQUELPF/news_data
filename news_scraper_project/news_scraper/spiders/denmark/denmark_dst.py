# 丹麦dst爬虫，负责抓取对应站点、机构或栏目内容。

import re

from bs4 import BeautifulSoup

import scrapy

from news_scraper.spiders.denmark.base import DenmarkBaseSpider


class DenmarkDstSpider(DenmarkBaseSpider):
    name = "denmark_dst"
    allowed_domains = ["dst.dk", "www.dst.dk"]
    target_table = "dnk_dst"
    start_urls = ["https://www.dst.dk/en/Statistik/udgivelser"]

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing)

    def parse_listing(self, response):
        html = self._fetch_html(self.start_urls[0])
        soup = BeautifulSoup(html, "html.parser")
        for row in soup.select(".release-row"):
            link = row.select_one(".flash-link a[href]")
            if not link:
                continue
            href = link.get("href")
            if not href:
                continue
            full_url = response.urljoin(href)
            if full_url in self.seen_urls:
                continue
            self.seen_urls.add(full_url)
            rel_text = self._clean_text(" ".join(row.select_one(".rel-type-date").stripped_strings)) if row.select_one(".rel-type-date") else ""
            publish_time = self._extract_publish_time(rel_text)
            if publish_time and not self.full_scan and publish_time < self.cutoff_date:
                continue
            try:
                detail_html = self._fetch_html(full_url)
            except Exception:
                continue
            detail_response = self._make_response(full_url, detail_html)
            item = next(self.parse_detail(detail_response, publish_time=publish_time), None)
            if item:
                yield item

    def parse_detail(self, response, publish_time=None):
        title = self._clean_text(
            response.xpath("//meta[@property='og:title']/@content").get()
            or response.css("h1::text").get()
            or response.css("title::text").get()
        )
        if not title or title == "Vi kan ikke finde siden, du leder efter":
            return

        final_publish_time = publish_time or self._extract_publish_time(
            self._clean_text(" ".join(response.css("main ::text").getall()[:120]))
        )
        if final_publish_time and not self.full_scan and final_publish_time < self.cutoff_date:
            return

        content = self._extract_content(response)
        if not content:
            return

        section = "analysis" if "/analysis/" in response.url else "publication"
        yield self._build_item(
            response=response,
            title=title,
            content=content,
            publish_time=final_publish_time,
            author="Statistics Denmark",
            language="en",
            section=section,
        )

    def _extract_publish_time(self, text):
        if not text:
            return None
        match = re.search(r"\b(\d{1,2}\.\d{1,2}\.\d{4})\b", text)
        if match:
            return self._parse_datetime(match.group(1), languages=["en"])
        return self._parse_datetime(text, languages=["en"])

    def _extract_content(self, response):
        soup = BeautifulSoup(response.text, "html.parser")
        root = soup.select_one(".alymainarea") or soup.select_one("main")
        if not root:
            return ""
        for unwanted in root.select("script, style, nav, footer, header, aside, form"):
            unwanted.decompose()
        parts = []
        for node in root.find_all(["p", "li"], recursive=True):
            text = self._clean_text(node.get_text(" ", strip=True))
            if not text or len(text) < 40:
                continue
            if text in {"Go to overview", "ON THIS PAGE"}:
                continue
            if text not in parts:
                parts.append(text)
        return "\n\n".join(parts)
