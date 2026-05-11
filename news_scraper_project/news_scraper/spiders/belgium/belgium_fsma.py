# 比利时fsma爬虫，负责抓取对应站点、机构或栏目内容。

from bs4 import BeautifulSoup

import scrapy

from news_scraper.spiders.belgium.base import BelgiumBaseSpider


class BelgiumFsmaSpider(BelgiumBaseSpider):
    name = "belgium_fsma"

    country_code = 'BEL'

    country = '比利时'
    allowed_domains = ["fsma.be", "www.fsma.be"]
    start_urls = ["https://www.fsma.be/en/news-articles"]

    async def start(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing, dont_filter=True)

    def parse_listing(self, response):
        for container in response.css('article, .node, .views-row, .teaser, li'):
            href = container.css('a[href^="/en/news/"]::attr(href)').get()
            if not href:
                continue
            full_url = response.urljoin(href)
            date_str = container.css('time::attr(datetime)').get()
            publish_time = self._parse_datetime(date_str, languages=["en"]) if date_str else None
            if not self.should_process(full_url, publish_time):
                continue
            yield scrapy.Request(full_url, callback=self.parse_detail)

    def parse_detail(self, response):
        title = self._clean_text(
            response.css("h1::text").get()
            or response.xpath("//meta[@property='og:title']/@content").get()
            or response.css("title::text").get()
        )
        if not title:
            return

        article_text = self._clean_text(" ".join(response.css("article ::text").getall()[:120]))
        publish_time = self._parse_datetime(article_text, languages=["en"])
        if publish_time and publish_time < self.cutoff_date:
            return

        content = self._extract_content(response)
        if not content:
            return

        section = "press_release" if "Press release" in article_text else "news"
        yield self._build_item(
            response=response,
            title=title,
            content=content,
            publish_time=publish_time,
            author="FSMA",
            language="en",
            section=section,
        )

    def _extract_content(self, response):
        soup = BeautifulSoup(response.text, "html.parser")
        root = soup.select_one("article") or soup.select_one(".node") or soup.select_one("main")
        if not root:
            return ""
        for unwanted in root.select("script, style, nav, footer, header, aside, form"):
            unwanted.decompose()
        parts = []
        for node in root.find_all(["p", "li"], recursive=True):
            text = self._clean_text(node.get_text(" ", strip=True))
            if not text or len(text) < 25:
                continue
            if text in {"This press release is not available in English. Please consult the French or Dutch ."}:
                continue
            if text not in parts:
                parts.append(text)
        return "\n\n".join(parts)

