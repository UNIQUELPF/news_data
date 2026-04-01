import re

import scrapy

from news_scraper.spiders.timor_leste.base import TimorLesteBaseSpider


class TimorLesteFinanceGovSpider(TimorLesteBaseSpider):
    name = "timor_leste_finance_gov"
    allowed_domains = ["mof.gov.tl", "mofwebadmin.mof.gov.tl"]
    target_table = "tls_finance_gov"
    verify_ssl = False
    api_url = "https://mofwebadmin.mof.gov.tl/api/publications"
    base_domain = "https://mofwebadmin.mof.gov.tl"

    def start_requests(self):
        yield scrapy.Request("https://www.mof.gov.tl/", callback=self.parse_listing)

    def parse_listing(self, response):
        try:
            payload = self._fetch_json(self.api_url)
        except Exception:
            return

        for row in payload.get("data", []):
            attrs = row.get("attributes", {})
            title = self._clean_text(attrs.get("title"))
            if not title:
                continue
            publish_time = self._parse_datetime(
                attrs.get("publishedAt") or attrs.get("updatedAt") or attrs.get("createdAt"),
                languages=["en", "pt"],
            )
            if publish_time and not self.full_scan and publish_time < self.cutoff_date:
                continue
            description = attrs.get("description") or ""
            links = re.findall(r'href="([^"]+\.pdf)"', description, flags=re.I)
            if not links:
                continue
            for href in links:
                full_url = href if href.startswith("http") else f"{self.base_domain}{href}"
                if full_url in self.seen_urls:
                    continue
                self.seen_urls.add(full_url)
                yield scrapy.Request(
                    full_url,
                    callback=self.parse_pdf,
                    cb_kwargs={"title": title, "publish_time": publish_time},
                )

    def parse_pdf(self, response, title, publish_time):
        content = self._extract_pdf_text(response.body, max_pages=6)
        if not content:
            content = title
        yield {
            "title": title,
            "content": content,
            "publish_time": publish_time,
            "url": response.url,
            "source_country": "Timor-Leste",
            "source_name": "Ministry of Finance Timor-Leste",
            "language": "en",
            "author": "Ministry of Finance Timor-Leste",
            "section": "government",
        }
