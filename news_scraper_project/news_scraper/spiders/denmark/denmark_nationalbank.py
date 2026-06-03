# 丹麦nationalbank爬虫，负责抓取对应站点、机构或栏目内容。
from bs4 import BeautifulSoup

import scrapy

from news_scraper.spiders.denmark.base import DenmarkBaseSpider


class DenmarkNationalbankSpider(DenmarkBaseSpider):
    name = "denmark_nationalbank"

    country_code = 'DNK'

    country = '丹麦'
    allowed_domains = ["nationalbanken.dk", "www.nationalbanken.dk"]
    start_urls = ["https://www.nationalbanken.dk/en/news-and-knowledge/publications-and-speeches/"]

    # Listing page has no dates; check dates on detail pages
    strict_date_required = False

    async def start(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing, dont_filter=True)

    def parse_listing(self, response):
        """
        Parse listing page: https://www.nationalbanken.dk/en/news-and-knowledge/publications-and-speeches/
        Links with /en/news-and-knowledge/publications-and-speeches/ sub-paths are article links.
        """
        seen = set()
        for link in response.css("a[href]"):
            href = link.attrib.get("href", "")
            if not href or "/en/news-and-knowledge/publications-and-speeches/" not in href:
                continue
            if any(part in href for part in ("/archive-speeches/", "/podcasts")):
                continue
            full_url = response.urljoin(href)
            if full_url.rstrip("/") == self.start_urls[0].rstrip("/"):
                continue
            if full_url in seen:
                continue
            seen.add(full_url)
            if not self.should_process(full_url):
                continue
            yield scrapy.Request(full_url, callback=self.parse_detail)

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
        if not self.should_process(response.url, publish_time):
            return

        content = self._do_extract_content(response)
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

    def _do_extract_content(self, response):
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
