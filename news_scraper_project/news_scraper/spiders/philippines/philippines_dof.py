# 菲律宾dof爬虫，负责抓取对应站点、机构或栏目内容。

import re

from bs4 import BeautifulSoup

import scrapy

from news_scraper.spiders.philippines.base import PhilippinesBaseSpider


class PhilippinesDofSpider(PhilippinesBaseSpider):
    name = "philippines_dof"

    country_code = 'PHL'

    country = '菲律宾'
    allowed_domains = ["dof.gov.ph", "www.dof.gov.ph"]
    start_urls = ["https://www.dof.gov.ph/news/"]

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing)

    def parse_listing(self, response):
        html = self._fetch_html(self.start_urls[0])
        soup = BeautifulSoup(html, "html.parser")
        for article in soup.select("article.post"):
            link = article.select_one("h1 a, h2 a, h3 a, .entry-title a, .thumbnail-link")
            if not link:
                continue
            href = (link.get("href") or "").strip()
            if not href.startswith("https://www.dof.gov.ph/"):
                continue
            if any(
                part in href
                for part in (
                    "/about/",
                    "/services/",
                    "/resources/",
                    "/statistical-data/",
                    "/contact-us/",
                    "/procurement/",
                    "/join-us/",
                    "/category/",
                    "/news/page/",
                )
            ):
                continue
            slug = href.replace("https://www.dof.gov.ph/", "").strip("/")
            if not slug or "/" in slug:
                continue
            if not re.search(r"[a-z]{4,}", slug):
                continue

            publish_text = self._clean_text(
                " ".join(article.select_one(".blog-entry-date").stripped_strings)
                if article.select_one(".blog-entry-date")
                else ""
            )
            publish_time = self._parse_datetime(publish_text, languages=["en"])
            if publish_time and not self.full_scan and publish_time < self.cutoff_date:
                continue

            if not self.should_process(href):
                continue
            yield scrapy.Request(href, callback=self.parse_detail)

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
            or self._clean_text(" ".join(response.css("main ::text, article ::text").getall()[:120])),
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
            author="Department of Finance",
            language="en",
            section="finance",
        )

    def _extract_content(self, response, title):
        soup = BeautifulSoup(response.text, "html.parser")
        root = soup.select_one("main") or soup.select_one("article") or soup.select_one(".entry-content")
        if not root:
            return ""
        for unwanted in root.select("script, style, nav, footer, header, aside, form, .share-links"):
            unwanted.decompose()
        title_text = self._clean_text(title)
        parts = []
        for node in root.find_all(["p", "li"], recursive=True):
            text = self._clean_text(node.get_text(" ", strip=True))
            if not text or len(text) < 35 or text == title_text:
                continue
            if text.startswith("Home") or text.startswith("DOF") or text.startswith("Share"):
                continue
            if text not in parts:
                parts.append(text)
        return "\n\n".join(parts)
