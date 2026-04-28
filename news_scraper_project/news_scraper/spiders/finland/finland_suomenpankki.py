# 芬兰suomenpankki爬虫，负责抓取对应站点、机构或栏目内容。

from bs4 import BeautifulSoup

import scrapy

from news_scraper.spiders.finland.base import FinlandBaseSpider


class FinlandSuomenpankkiSpider(FinlandBaseSpider):
    name = "finland_suomenpankki"

    country_code = 'FIN'

    country = '芬兰'
    allowed_domains = ["suomenpankki.fi", "www.suomenpankki.fi"]
    start_urls = ["https://www.suomenpankki.fi/en/news-and-topical/press-releases-and-news/"]

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing)

    def parse_listing(self, response):
        html = self._fetch_html(self.start_urls[0])
        soup = BeautifulSoup(html, "html.parser")
        for link in soup.select("a[href]"):
            href = (link.get("href") or "").strip()
            if not href.startswith("/en/news-and-topical/press-releases-and-news/"):
                continue
            if "/releases/" not in href and "/news/" not in href:
                continue
            if href.endswith("/releases/") or href.endswith("/news/"):
                continue
            full_url = response.urljoin(href.split("?")[0])
            if not self.should_process(full_url):
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
            or response.css("h1::text").get()
            or response.css("title::text").get()
        )
        if not title:
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
            author="Bank of Finland",
            language="en",
            section="central_bank",
        )

    def _extract_content(self, response):
        soup = BeautifulSoup(response.text, "html.parser")
        root = soup.select_one("main") or soup.select_one(".main-content") or soup.select_one(".article")
        if not root:
            return ""
        for unwanted in root.select("script, style, nav, footer, header, aside, form, .share, .related-content"):
            unwanted.decompose()
        parts = []
        for node in root.find_all(["p", "li"], recursive=True):
            text = self._clean_text(node.get_text(" ", strip=True))
            if not text or len(text) < 35:
                continue
            if text not in parts:
                parts.append(text)
        return "\n\n".join(parts)

