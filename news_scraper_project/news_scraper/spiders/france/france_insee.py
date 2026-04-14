# 法国insee爬虫，负责抓取对应站点、机构或栏目内容。

import re

from bs4 import BeautifulSoup

import scrapy

from news_scraper.spiders.france.base import FranceBaseSpider


class FranceInseeSpider(FranceBaseSpider):
    name = "france_insee"

    country_code = 'FRA'

    country = '法国'
    allowed_domains = ["insee.fr", "www.insee.fr"]
    target_table = "fra_insee"
    start_urls = ["https://www.insee.fr/fr/accueil"]

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing)

    def parse_listing(self, response):
        html = self._fetch_html(self.start_urls[0])
        urls = sorted(set(re.findall(r'https://www\.insee\.fr/fr/statistiques/\d+|/fr/statistiques/\d+', html)))
        for href in urls:
            full_url = response.urljoin(href)
            if full_url in self.seen_urls:
                continue
            if not self.full_scan:
                article_id = re.search(r"/(\d+)$", full_url)
                if article_id and int(article_id.group(1)) < 8000000:
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
            or self._clean_text(" ".join(response.css("body ::text").getall()[:120])),
            languages=["fr", "en"],
        )
        if publish_time and not self.full_scan and publish_time < self.cutoff_date:
            return

        content = self._extract_content(response, title)
        if not content:
            content = self._clean_text(response.xpath("//meta[@name='description']/@content").get())
        if not content:
            return

        yield self._build_item(
            response=response,
            title=title.replace("| Insee", "").strip(),
            content=content,
            publish_time=publish_time,
            author="INSEE",
            language="fr",
            section="statistics",
        )

    def _extract_content(self, response, title):
        soup = BeautifulSoup(response.text, "html.parser")
        root = soup.select_one("main") or soup.select_one("article")
        if not root:
            return ""
        for unwanted in root.select("script, style, nav, footer, header, aside, form, .sommaire"):
            unwanted.decompose()
        title_text = self._clean_text(title)
        parts = []
        for node in root.find_all(["p", "li"], recursive=True):
            text = self._clean_text(node.get_text(" ", strip=True))
            if not text or len(text) < 35 or text == title_text:
                continue
            if text.startswith("Source :") or text.startswith("Partager"):
                continue
            if text not in parts:
                parts.append(text)
        return "\n\n".join(parts)
