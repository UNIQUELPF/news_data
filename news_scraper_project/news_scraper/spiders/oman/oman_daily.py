# 阿曼daily爬虫，负责抓取对应站点、机构或栏目内容。

from bs4 import BeautifulSoup

import scrapy

from news_scraper.spiders.oman.base import OmanBaseSpider


# 阿曼经济类来源
# 站点：Oman Daily
# 入库表：omn_oman_daily
# 语言：阿拉伯语


class OmanDailySpider(OmanBaseSpider):
    """阿曼日报经济栏目。

    站点：https://www.omandaily.om
    栏目：الاقتصادية
    入库表：omn_oman_daily
    """

    name = "oman_daily"
    allowed_domains = ["omandaily.om", "www.omandaily.om"]
    target_table = "omn_oman_daily"
    start_urls = [
        "https://www.omandaily.om/morearticles/%D8%A7%D9%84%D8%A7%D9%82%D8%AA%D8%B5%D8%A7%D8%AF%D9%8A%D8%A9",
    ]

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing, meta={"dont_verify_ssl": True})

    def parse_listing(self, response):
        links = response.css("a::attr(href)").getall()
        for href in links:
            full_url = response.urljoin(href)
            if "/%D8%A7%D9%84%D8%A7%D9%82%D8%AA%D8%B5%D8%A7%D8%AF%D9%8A%D8%A9/na/" not in full_url and "/الاقتصادية/na/" not in full_url:
                continue
            if full_url in self.seen_urls:
                continue
            self.seen_urls.add(full_url)
            yield scrapy.Request(full_url, callback=self.parse_detail, meta={"dont_verify_ssl": True})

    def parse_detail(self, response):
        title = self._clean_text(
            response.xpath("//meta[@property='og:title']/@content").get()
            or response.css("h1::text").get()
        )
        if not title or "الموقع الرسمي لجريدة عمان" in title:
            return

        content = self._extract_content(response, title)
        if not content:
            return

        publish_time = self._parse_datetime(
            "".join(response.xpath("//body//text()[contains(., '2026') or contains(., '2025')][1]").getall()),
            languages=["ar"],
        )
        if publish_time and not self.full_scan and publish_time < self.cutoff_date:
            return

        yield self._build_item(
            response=response,
            title=title.replace(" - الموقع الرسمي لجريدة عمان", "").strip(),
            content=content,
            publish_time=publish_time,
            author="Oman Daily",
            language="ar",
            section="economy",
        )

    def _extract_content(self, response, title):
        soup = BeautifulSoup(response.text, "html.parser")
        root = soup.select_one("main") or soup.select_one("article") or soup.body
        if not root:
            return ""

        for unwanted in root.select("script, style, nav, footer, header, aside, form, .share, .related"):
            unwanted.decompose()

        title_text = self._clean_text(title)
        parts = []
        for node in root.find_all(["p", "h2", "h3", "li"], recursive=True):
            text = self._clean_text(node.get_text(" ", strip=True))
            if not text or len(text) < 20:
                continue
            if text == title_text or text == "الاقتصادية":
                continue
            if "الموقع الرسمي لجريدة عمان" in text:
                continue
            if text not in parts:
                parts.append(text)

        return "\n\n".join(parts)
