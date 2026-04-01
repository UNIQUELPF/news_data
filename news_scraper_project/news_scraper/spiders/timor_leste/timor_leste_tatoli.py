import re

from bs4 import BeautifulSoup

import scrapy

from news_scraper.spiders.timor_leste.base import TimorLesteBaseSpider


class TimorLesteTatoliSpider(TimorLesteBaseSpider):
    name = "timor_leste_tatoli"
    allowed_domains = ["en.tatoli.tl", "tatoli.tl"]
    target_table = "tls_tatoli"
    start_urls = ["https://en.tatoli.tl/"]

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing)

    def parse_listing(self, response):
        html = self._fetch_html(self.start_urls[0])
        for full_url in sorted(set(re.findall(r"https://en\.tatoli\.tl/\d{4}/\d{2}/\d{2}/[^\"' ]+", html))):
            full_url = full_url.rstrip("/")
            if full_url in self.seen_urls:
                continue
            year_match = re.search(r"/(20\d{2})/", full_url)
            if year_match and not self.full_scan and int(year_match.group(1)) < self.cutoff_date.year:
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
            response.xpath("//meta[@property='article:published_time']/@content").get()
            or response.xpath("//time/@datetime").get()
            or " ".join(response.css("body ::text").getall()[:100]),
            languages=["en"],
        )
        if publish_time and not self.full_scan and publish_time < self.cutoff_date:
            return
        content = self._extract_content(response, title)
        if not content:
            content = self._clean_text(response.xpath("//meta[@property='og:description']/@content").get())
        if not content:
            return
        yield self._build_item(
            response=response,
            title=title,
            content=content,
            publish_time=publish_time,
            author="TATOLI",
            language="en",
            section="economy",
        )

    def _extract_content(self, response, title):
        soup = BeautifulSoup(response.text, "html.parser")
        root = soup.select_one("article") or soup.select_one(".single-content") or soup.select_one("main")
        if not root:
            return ""
        for unwanted in root.select("script, style, nav, footer, header, aside, form, .sharedaddy, .jp-relatedposts"):
            unwanted.decompose()
        title_text = self._clean_text(title)
        parts = []
        for node in root.find_all(["p", "li"], recursive=True):
            text = self._clean_text(node.get_text(" ", strip=True))
            if not text or len(text) < 35 or text == title_text:
                continue
            if text not in parts:
                parts.append(text)
        return "\n\n".join(parts)
