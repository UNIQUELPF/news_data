# 巴林tra爬虫，负责抓取对应站点、机构或栏目内容。

from bs4 import BeautifulSoup

import scrapy

from news_scraper.spiders.bahrain.base import BahrainBaseSpider


class BahrainTraSpider(BahrainBaseSpider):
    name = "bahrain_tra"
    allowed_domains = ["tra.org.bh", "www.tra.org.bh"]
    target_table = "bhr_tra"
    start_urls = [
        "https://www.tra.org.bh/category/press-releases/",
    ]

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing)

    def parse_listing(self, response):
        for href in response.css("a[href*='/article/']::attr(href)").getall():
            href = href.strip()
            if href.startswith("../article/"):
                full_url = response.urljoin("/" + href[3:])
            else:
                full_url = response.urljoin(href)
            if full_url in self.seen_urls:
                continue
            self.seen_urls.add(full_url)
            yield scrapy.Request(full_url, callback=self.parse_detail)

    def parse_detail(self, response):
        title = self._clean_text(
            response.css(".page-title::text, main h2::text").get()
            or response.xpath("//meta[@property='og:title']/@content").get()
            or response.css("title::text").get()
        )
        if not title or title == "البيانات الصحفية":
            return

        main_text = self._clean_text(" ".join(response.css("main ::text").getall()))
        publish_time = self._parse_datetime(main_text, languages=["ar", "en"])
        if publish_time and not self.full_scan and publish_time < self.cutoff_date:
            return

        content = self._extract_content(response, title)
        if not content:
            return

        yield self._build_item(
            response=response,
            title=title,
            content=content,
            publish_time=publish_time,
            author="TRA Bahrain",
            language="ar",
            section="press_release",
        )

    def _extract_content(self, response, title):
        soup = BeautifulSoup(response.text, "html.parser")
        root = soup.select_one("main")
        if not root:
            return ""

        for unwanted in root.select("script, style, nav, footer, header, aside, form"):
            unwanted.decompose()

        title_text = self._clean_text(title)
        parts = []
        started = False
        for node in root.find_all(["h2", "p", "li"], recursive=True):
            text = self._clean_text(node.get_text(" ", strip=True))
            if not text:
                continue
            if text == title_text:
                started = True
                continue
            if not started:
                continue
            if text in {"روابط سريعة", "TRABahrain", "الاشتراك في النشرة الإخبارية"}:
                break
            if len(text) < 20:
                continue
            if text not in parts:
                parts.append(text)
        return "\n\n".join(parts)
