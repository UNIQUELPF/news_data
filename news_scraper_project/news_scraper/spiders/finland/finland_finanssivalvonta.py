# 芬兰finanssivalvonta爬虫，负责抓取对应站点、机构或栏目内容。

from bs4 import BeautifulSoup

import scrapy

from news_scraper.spiders.finland.base import FinlandBaseSpider


class FinlandFinanssivalvontaSpider(FinlandBaseSpider):
    name = "finland_finanssivalvonta"

    country_code = 'FIN'

    country = '芬兰'
    allowed_domains = ["finanssivalvonta.fi", "www.finanssivalvonta.fi"]
    target_table = "fin_finanssivalvonta"
    start_urls = [
        "https://www.finanssivalvonta.fi/en/publications-and-press-releases/news-releases/2025/",
        "https://www.finanssivalvonta.fi/en/publications-and-press-releases/news-releases/2026/",
    ]

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing)

    def parse_listing(self, response):
        html = self._fetch_html(response.url)
        soup = BeautifulSoup(html, "html.parser")
        for link in soup.select("a[href]"):
            href = (link.get("href") or "").strip()
            if not href.startswith("/en/publications-and-press-releases/news-releases/"):
                continue
            if href.endswith("/2025/") or href.endswith("/2026/") or href.endswith("/news-releases/"):
                continue
            if href.count("/") < 6:
                continue
            full_url = response.urljoin(href.split("?")[0].rstrip("/") + "/")
            if full_url.rstrip("/") == response.url.rstrip("/"):
                continue
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
        if not title or title == "Sivua ei löytynyt":
            return

        publish_time = self._parse_datetime(
            response.xpath("//meta[@property='article:published_time']/@content").get()
            or self._clean_text(" ".join(response.css("body ::text").getall()[:120])),
            languages=["en"],
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
            author="FIN-FSA",
            language="en",
            section="financial_regulator",
        )

    def _extract_content(self, response):
        soup = BeautifulSoup(response.text, "html.parser")
        root = soup.select_one("main") or soup.select_one("article") or soup.select_one(".page-content")
        if not root:
            return ""
        for unwanted in root.select("script, style, nav, footer, header, aside, form, .share, .subnavigation"):
            unwanted.decompose()
        parts = []
        for node in root.find_all(["p", "li"], recursive=True):
            text = self._clean_text(node.get_text(" ", strip=True))
            if not text or len(text) < 35:
                continue
            if text.startswith("Go to content") or text.startswith("Published"):
                continue
            if text not in parts:
                parts.append(text)
        return "\n\n".join(parts)
