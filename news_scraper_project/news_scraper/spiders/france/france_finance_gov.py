# 法国finance gov爬虫，负责抓取对应站点、机构或栏目内容。

import re

from bs4 import BeautifulSoup

import scrapy

from news_scraper.spiders.france.base import FranceBaseSpider


class FranceFinanceGovSpider(FranceBaseSpider):
    name = "france_finance_gov"

    country_code = 'FRA'

    country = '法国'
    allowed_domains = ["presse.economie.gouv.fr", "economie.gouv.fr"]
    start_urls = ["https://presse.economie.gouv.fr/"]

    fallback_content_selector = "article, main"

    # Listing page has no dates; check dates on detail pages
    strict_date_required = False
    use_curl_cffi = True

    async def start(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing, dont_filter=True)

    def parse_listing(self, response):
        if self._stop_pagination:
            return
        seen = set()
        for link in response.css("a[href]"):
            href = (link.attrib.get("href") or "").strip()
            if not href.startswith("https://presse.economie.gouv.fr/") and not href.startswith("/"):
                continue
            full_url = response.urljoin(href)
            path = full_url.replace("https://presse.economie.gouv.fr", "")
            if not re.match(r"^/[a-z0-9][a-z0-9\\-]*/?$", path, re.I):
                continue
            if path in {"", "/"}:
                continue
            if any(path.startswith(prefix) for prefix in ("/agendas", "/medias", "/selection", "/le-ministere")):
                continue
            if full_url in seen:
                continue
            seen.add(full_url)
            if not self.should_process(full_url, None):
                continue
            yield scrapy.Request(full_url, callback=self.parse_detail)

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
            or response.xpath("//meta[@name='article:published_time']/@content").get()
            or response.xpath("//meta[@name='date']/@content").get()
            or response.xpath("//time/@datetime").get()
            or response.css("time::attr(datetime)").get(),
            languages=["fr", "en"],
        )
        if not self.should_process(response.url, publish_time):
            self._stop_pagination = True
            return

        content = self._do_extract_content(response, title)
        if not content:
            content = self._clean_text(response.xpath("//meta[@name='description']/@content").get())
        if not content:
            return

        yield self._build_item(
            response=response,
            title=title.replace(" - Presse – Ministère de l'Économie, des Finances et de la Souveraineté industrielle et numérique", "").strip(),
            content=content,
            publish_time=publish_time,
            author="Ministère de l'Économie",
            language="fr",
            section="finance",
        )

    def _do_extract_content(self, response, title):
        soup = BeautifulSoup(response.text, "html.parser")
        root = soup.select_one("main") or soup.select_one("article")
        if not root:
            return ""
        for unwanted in root.select("script, style, nav, footer, header, aside, form"):
            unwanted.decompose()
        title_text = self._clean_text(title)
        parts = []
        for node in root.find_all(["p", "li", "h2", "h3"], recursive=True):
            text = self._clean_text(node.get_text(" ", strip=True))
            if not text or len(text) < 20 or text == title_text:
                continue
            if text.startswith("Publié le") or text.startswith("Partager"):
                continue
            if text not in parts:
                parts.append(text)
        return "\n\n".join(parts)
