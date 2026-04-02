# 法国amf爬虫，负责抓取对应站点、机构或栏目内容。

import re

from bs4 import BeautifulSoup

import scrapy

from news_scraper.spiders.france.base import FranceBaseSpider


class FranceAmfSpider(FranceBaseSpider):
    name = "france_amf"
    allowed_domains = ["amf-france.org", "www.amf-france.org"]
    target_table = "fra_amf"
    start_urls = [
        "https://www.amf-france.org/fr/actualites-publications/communiques/communiques-de-lamf",
        "https://www.amf-france.org/fr/actualites-publications/actualites",
    ]

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing)

    def parse_listing(self, response):
        html = self._fetch_html(response.url)
        soup = BeautifulSoup(html, "html.parser")
        for link in soup.select("a[href^='/fr/actualites-publications/']"):
            href = link.get("href") or ""
            if href.rstrip("/") in {"/fr/actualites-publications/communiques/communiques-de-lamf", "/fr/actualites-publications/actualites"}:
                continue
            if any(
                segment in href
                for segment in (
                    "/agenda",
                    "/la-une",
                    "/dossiers-thematiques",
                    "/publications/",
                    "/evenements-de-lamf/",
                    "/positions-ue-de-lamf",
                    "/consultations-de-lamf",
                )
            ):
                continue
            if href.count("/") < 5:
                continue
            full_url = response.urljoin(href)
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
        if not title:
            return

        publish_time = self._parse_datetime(
            response.xpath("//meta[@property='article:published_time']/@content").get()
            or self._extract_publish_text(response),
            languages=["fr", "en"],
        )
        if publish_time and not self.full_scan and publish_time < self.cutoff_date:
            return

        content = self._extract_content(response, title)
        if not content:
            content = self._clean_text(response.xpath("//meta[@name='description']/@content").get())
        if not content:
            return

        section = "press_release" if "/communiques/" in response.url else "news"
        yield self._build_item(
            response=response,
            title=title.replace("| AMF", "").strip(),
            content=content,
            publish_time=publish_time,
            author="AMF France",
            language="fr",
            section=section,
        )

    def _extract_publish_text(self, response):
        text = self._clean_text(" ".join(response.css("article ::text, main ::text").getall()[:160]))
        match = re.search(
            r"Publié le\s+(\d{1,2}\s+[A-Za-zéûôîàèùç]+\s+\d{4})",
            text,
            flags=re.IGNORECASE,
        )
        if match:
            return match.group(1)
        return text

    def _extract_content(self, response, title):
        soup = BeautifulSoup(response.text, "html.parser")
        root = soup.select_one("main") or soup.select_one("article")
        if not root:
            return ""
        for unwanted in root.select("script, style, nav, footer, header, aside, form"):
            unwanted.decompose()
        title_text = self._clean_text(title)
        parts = []
        for node in root.find_all(["p", "li"], recursive=True):
            text = self._clean_text(node.get_text(" ", strip=True))
            if not text or len(text) < 30 or text == title_text:
                continue
            if text.startswith("Publié le") or text.startswith("En savoir plus"):
                continue
            if text not in parts:
                parts.append(text)
        return "\n\n".join(parts)
