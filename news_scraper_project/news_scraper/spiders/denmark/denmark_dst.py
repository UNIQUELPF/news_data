# 丹麦dst爬虫，负责抓取对应站点、机构或栏目内容。
import re

import scrapy

from news_scraper.spiders.denmark.base import DenmarkBaseSpider


class DenmarkDstSpider(DenmarkBaseSpider):
    name = "denmark_dst"

    country_code = 'DNK'

    country = '丹麦'
    allowed_domains = ["dst.dk", "www.dst.dk"]
    start_urls = ["https://www.dst.dk/en/Statistik/udgivelser"]

    async def start(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing, dont_filter=True)

    def parse_listing(self, response):
        """
        Parse listing page: https://www.dst.dk/en/Statistik/udgivelser
        Each item has a .release-row div with .rel-type-date and .flash-link a[href]
        Example date text: "Publication / 28.4.2026"
        """
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.text, "html.parser")
        for row in soup.select(".release-row"):
            link = row.select_one(".flash-link a[href]")
            if not link:
                continue
            href = link.get("href")
            if not href:
                continue
            full_url = response.urljoin(href)

            rel_text = ""
            rel_node = row.select_one(".rel-type-date")
            if rel_node:
                rel_text = self._clean_text(rel_node.get_text(" ", strip=True))

            publish_time = self._extract_publish_time(rel_text)

            if not self.should_process(full_url, publish_time):
                continue

            yield scrapy.Request(
                full_url,
                callback=self.parse_detail,
                meta={"publish_time": publish_time},
            )

    def parse_detail(self, response):
        publish_time = response.meta.get("publish_time")

        title = self._clean_text(
            response.xpath("//meta[@property='og:title']/@content").get()
            or response.css("h1::text").get()
            or response.css("title::text").get()
        )
        if not title or title == "Vi kan ikke finde siden, du leder efter":
            return

        if not publish_time:
            publish_time = self._extract_publish_time(
                self._clean_text(" ".join(response.css("main ::text").getall()[:120]))
            )
        if not self.should_process(response.url, publish_time):
            return

        from bs4 import BeautifulSoup
        content = self._do_extract_content(response)
        if not content:
            return

        section = "analysis" if "/analysis/" in response.url else "publication"
        yield self._build_item(
            response=response,
            title=title,
            content=content,
            publish_time=publish_time,
            author="Statistics Denmark",
            language="en",
            section=section,
        )

    def _extract_publish_time(self, text):
        if not text:
            return None
        # Matches "28.4.2026" or "28.04.2026"
        match = re.search(r"\b(\d{1,2}\.\d{1,2}\.\d{4})\b", text)
        if match:
            return self._parse_datetime(match.group(1), languages=["en"])
        return self._parse_datetime(text, languages=["en"])

    def _do_extract_content(self, response):
        from bs4 import BeautifulSoup
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
