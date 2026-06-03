# 芬兰vm爬虫，负责抓取对应站点、机构或栏目内容。
from bs4 import BeautifulSoup

import scrapy

from news_scraper.spiders.finland.base import FinlandBaseSpider


class FinlandVmSpider(FinlandBaseSpider):
    name = "finland_vm"

    country_code = 'FIN'

    country = '芬兰'
    allowed_domains = ["vm.fi", "www.vm.fi"]
    start_urls = ["https://vm.fi/en/press-releases"]

    # Listing page has no dates; check dates on detail pages
    strict_date_required = False

    async def start(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing, dont_filter=True)

    def parse_listing(self, response):
        seen = set()
        for link in response.css("a[href]"):
            href = (link.attrib.get("href") or "").strip()
            if "/en/-/" not in href:
                continue
            full_url = response.urljoin(href.split("?")[0])
            if full_url in seen:
                continue
            seen.add(full_url)
            if not self.should_process(full_url, None):
                continue
            yield scrapy.Request(full_url, callback=self.parse_detail)

    def parse_detail(self, response):
        title = self._clean_text(
            response.xpath("//meta[@property='og:title']/@content").get()
            or response.css("h1::text").get()
            or response.css("title::text").get()
        )
        if not title:
            return

        publish_time = self._parse_datetime(
            response.xpath("//meta[@property='article:published_time']/@content").get()
            or response.xpath("//meta[@name='date']/@content").get()
            or self._clean_text(" ".join(response.css("body ::text").getall()[:120])),
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
            author="Ministry of Finance Finland",
            language="en",
            section="finance",
        )

    def _do_extract_content(self, response):
        soup = BeautifulSoup(response.text, "html.parser")
        root = (
            soup.select_one("article")
            or soup.select_one("main")
            or soup.select_one(".journal-content-article")
            or soup.select_one(".content-area")
        )
        if not root:
            return ""
        for unwanted in root.select("script, style, nav, footer, header, aside, form, .social-media-share, .portlet-breadcrumb"):
            unwanted.decompose()
        parts = []
        for node in root.find_all(["p", "li"], recursive=True):
            text = self._clean_text(node.get_text(" ", strip=True))
            if not text or len(text) < 35:
                continue
            if text.startswith("Ministry of Finance") or text.startswith("Share"):
                continue
            if text not in parts:
                parts.append(text)
        return "\n\n".join(parts)
