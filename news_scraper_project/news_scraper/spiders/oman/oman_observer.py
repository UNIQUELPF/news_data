from bs4 import BeautifulSoup

import scrapy

from news_scraper.spiders.oman.base import OmanBaseSpider


# 阿曼经济类来源
# 站点：Oman Observer
# 入库表：omn_oman_observer
# 语言：英语


class OmanObserverSpider(OmanBaseSpider):
    """阿曼观察家报经济栏目。

    站点：https://www.omanobserver.om
    栏目：business / economy
    入库表：omn_oman_observer
    """

    name = "oman_observer"
    allowed_domains = ["omanobserver.om", "www.omanobserver.om"]
    target_table = "omn_oman_observer"
    start_urls = [
        "https://www.omanobserver.om/morearticles/business/economy",
    ]

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing, meta={"dont_verify_ssl": True})

    def parse_listing(self, response):
        links = response.css('a[href*="/article/"]::attr(href)').getall()
        for href in links:
            full_url = response.urljoin(href)
            if "/business/economy/" not in full_url or full_url in self.seen_urls:
                continue
            self.seen_urls.add(full_url)
            yield scrapy.Request(full_url, callback=self.parse_detail, meta={"dont_verify_ssl": True})

        next_page = response.css("a[rel='next']::attr(href)").get()
        if next_page:
            yield response.follow(next_page, callback=self.parse_listing, meta={"dont_verify_ssl": True})

    def parse_detail(self, response):
        title = self._clean_text(
            response.xpath("//meta[@property='og:title']/@content").get()
            or response.css("h1::text").get()
        )
        if not title:
            return

        publish_time = self._parse_datetime(
            response.xpath("//meta[@property='article:published_time']/@content").get()
            or response.xpath("//meta[@name='datePublished']/@content").get(),
            languages=["en"],
        )
        if publish_time and not self.full_scan and publish_time < self.cutoff_date:
            return

        content = self._extract_content(response)
        if not content:
            content = self._clean_text(response.xpath("//meta[@name='description']/@content").get())
        if not content:
            return

        yield self._build_item(
            response=response,
            title=title.replace(" - Oman Observer", "").strip(),
            content=content,
            publish_time=publish_time,
            author=self._clean_text(response.xpath("//meta[@name='author']/@content").get()) or "Oman Observer",
            language="en",
            section="economy",
        )

    def _extract_content(self, response):
        soup = BeautifulSoup(response.text, "html.parser")
        root = (
            soup.select_one(".article-content")
            or soup.select_one("[itemprop='articleBody']")
            or soup.select_one("article")
            or soup.select_one("main")
        )
        if not root:
            return ""

        for unwanted in root.select("script, style, nav, footer, header, aside, form, .share, .related"):
            unwanted.decompose()

        parts = []
        for node in root.find_all(["p", "h2", "h3", "li"], recursive=True):
            text = self._clean_text(node.get_text(" ", strip=True))
            if not text or len(text) < 25 or text == "SHARE":
                continue
            if text not in parts:
                parts.append(text)
        return "\n\n".join(parts)
