import re
import xml.etree.ElementTree as ET

import requests

from news_scraper.spiders.smart_spider import SmartSpider


class USAReutersSpider(SmartSpider):
    name = "usa_reuters"
    source_name = "Reuters Finance"
    organization = "Reuters"
    source_timezone = "America/New_York"
    country_code = "USA"
    country = "美国"
    language = "en"
    allowed_domains = ["reuters.com"]
    strict_date_required = True
    use_curl_cffi = False
    dateparser_settings = {"DATE_ORDER": "MDY"}
    section_name = "Finance"

    sitemap_index = "https://www.reuters.com/arc/outboundfeeds/news-sitemap-index/?outputType=xml"
    include_url_patterns = ("/business/", "/markets/", "/legal/government/")

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_DELAY": 0.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
    }

    async def start(self):
        for item in self._iter_sitemap_items():
            yield item

    def _iter_sitemap_items(self):
        ns = {
            "sm": "http://www.sitemaps.org/schemas/sitemap/0.9",
            "news": "http://www.google.com/schemas/sitemap-news/0.9",
        }
        try:
            index_text = requests.get(self.sitemap_index, timeout=30, verify=False).text
            index_root = ET.fromstring(index_text.encode("utf-8"))
        except Exception as exc:
            self.logger.error(f"Reuters sitemap index failed: {exc}")
            return

        sitemap_urls = [node.text for node in index_root.findall(".//sm:loc", ns) if node.text]
        for sitemap_url in sitemap_urls[:5]:
            try:
                text = requests.get(sitemap_url, timeout=30, verify=False).text
                root = ET.fromstring(text.encode("utf-8"))
            except Exception as exc:
                self.logger.error(f"Reuters sitemap failed {sitemap_url}: {exc}")
                continue

            for node in root.findall(".//sm:url", ns):
                url = node.findtext("sm:loc", namespaces=ns)
                if not url or not any(pattern in url for pattern in self.include_url_patterns):
                    continue
                date_text = (
                    node.findtext("news:news/news:publication_date", namespaces=ns)
                    or node.findtext("sm:lastmod", namespaces=ns)
                )
                publish_time = self.parse_date(date_text)
                if not publish_time or not self.should_process(url, publish_time):
                    continue
                title = node.findtext("news:news/news:title", namespaces=ns) or self._title_from_url(url)
                raw_xml = ET.tostring(node, encoding="unicode")
                content = title
                yield {
                    "url": url,
                    "title": title,
                    "raw_html": raw_xml,
                    "content_cleaned": content,
                    "content_markdown": content,
                    "content_plain": content,
                    "images": [],
                    "publish_time": publish_time,
                    "author": "Reuters",
                    "language": self.language,
                    "section": self.section_name,
                    "category": self.section_name,
                    "country_code": self.country_code,
                    "country": self.country,
                    "organization": self.organization,
                }

    def _title_from_url(self, url):
        slug = url.rstrip("/").split("/")[-2] if url.rstrip("/").endswith("2026-06-04") else url.rstrip("/").split("/")[-1]
        slug = re.sub(r"-\d{4}-\d{2}-\d{2}$", "", slug)
        return slug.replace("-", " ").title()
