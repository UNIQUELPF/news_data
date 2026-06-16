import scrapy
from news_scraper.spiders.smart_spider import SmartSpider

class UkItproSpider(SmartSpider):
    name = "uk_itpro"
    allowed_domains = ['itpro.com']
    start_urls = ['https://www.itpro.com/business/business-strategy']
    source_timezone = "Europe/London"

    country_code = "GBR"
    country = "英国"
    language = "en"

    fallback_content_selector = "article, main, [role='main'], .article-body, .content"
    strict_date_required = False
    use_curl_cffi = True
    curl_cffi_verify = True

    async def start(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing, dont_filter=True)

    def parse_listing(self, response):
        if self._stop_pagination:
            return

        seen = set()
        all_links = response.css("a[href]")
        for a_sel in all_links:
            href = a_sel.attrib.get("href", "").strip()
            if not href or any(x in href for x in ["javascript:", "mailto:", "#"]):
                continue

            url = response.urljoin(href).split("#")[0]

            # Limit to allowed domains
            if not any(dom in url for dom in self.allowed_domains):
                continue

            # Skip obvious static non-article resources
            if url.rstrip("/") == response.url.rstrip("/"):
                continue
            if any(url.lower().endswith(ext) for ext in [".pdf", ".zip", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx"]):
                continue

            if url in seen:
                continue
            seen.add(url)

            if not self.should_process(url, None):
                continue

            yield scrapy.Request(url, callback=self.parse_detail)

    def parse_detail(self, response):
        if not isinstance(response, scrapy.http.TextResponse):
            return

        item = self.auto_parse_item(response)
        
        # Override metadata to ensure they match target values
        item["author"] = "ITPro"
        item["section"] = "Business Strategy"

        if item.get("content_plain") and len(item["content_plain"]) > 50:
            yield item
