# 德国finance gov爬虫，负责抓取对应站点、机构或栏目内容。

import re

from bs4 import BeautifulSoup

import scrapy

from news_scraper.spiders.germany.base import GermanyBaseSpider


class GermanyFinanceGovSpider(GermanyBaseSpider):
    name = "germany_finance_gov"

    country_code = 'DEU'

    country = '德国'
    allowed_domains = ["bundesfinanzministerium.de", "www.bundesfinanzministerium.de"]
    start_urls = ["https://www.bundesfinanzministerium.de/Web/EN/Press/Press_releases/press_releases.html"]
    base_domain = "https://www.bundesfinanzministerium.de"

    # Listing page has no dates; check dates on detail pages
    strict_date_required = False
    use_curl_cffi = True

    async def start(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing, dont_filter=True)

    def parse_listing(self, response):
        seen = set()
        for link in response.css("a[href]"):
            href = (link.attrib.get("href") or "").strip()
            if "Content/EN/Pressemitteilungen/" not in href:
                continue
            full_url = self.base_domain + href.split(";")[0].split("?")[0] if href.startswith("/") else f"{self.base_domain}/{href.split(';')[0].split('?')[0].lstrip('/')}"
            if not full_url.endswith(".html"):
                continue
            if full_url in seen:
                continue
            seen.add(full_url)
            year_match = re.search(r"/(20\d{2})/", full_url)
            if year_match and int(year_match.group(1)) < self.cutoff_date.year:
                continue
            if not self.should_process(full_url, None):
                continue
            yield scrapy.Request(full_url, callback=self.parse_detail)

    def parse_detail(self, response):
        title = self._clean_text(
            response.xpath("//meta[@property='og:title']/@content").get()
            or response.css("h1::text").get()
            or response.css("title::text").get()
        )
        if not title or "not found" in title.lower():
            return

        publish_time = self._parse_datetime(
            self._clean_text(
                response.xpath("//time/@datetime").get()
                or " ".join(response.css("body ::text").getall()[:120])
            ),
            languages=["de", "en"],
        )
        if not self.should_process(response.url, publish_time):
            return

        content = self._do_extract_content(response)
        if not content:
            return

        yield self._build_item(
            response=response,
            title=title,
            content=content,
            publish_time=publish_time,
            author="Federal Ministry of Finance",
            language="en",
            section="finance",
        )

    def _do_extract_content(self, response):
        soup = BeautifulSoup(response.text, "html.parser")
        root = (
            soup.select_one(".article-text.singleview")
            or soup.select_one(".article-text-wrapper")
            or soup.select_one(".article-wrapper")
            or soup.select_one("#content")
            or soup.select_one("main")
        )
        if not root:
            return ""
        for unwanted in root.select("script, style, nav, footer, header, aside, form, .bmf-toolbox, .bmf-share, .modal, .bmf-sitemap"):
            unwanted.decompose()
        parts = []
        for node in root.find_all(["p", "li"], recursive=True):
            text = self._clean_text(node.get_text(" ", strip=True))
            if not text or len(text) < 35:
                continue
            if text.startswith("Consent for statistical analysis") or text.startswith("Allow") or text.startswith("Reject"):
                continue
            if "If you have any further questions, please contact webmaster@bmf.bund.de" in text:
                continue
            if text not in parts:
                parts.append(text)
        return "\n\n".join(parts)
