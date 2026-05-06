import scrapy
import json
from datetime import datetime
from news_scraper.spiders.smart_spider import SmartSpider

class EeEmtaSpider(SmartSpider):
    name = "ee_emta"

    country_code = 'EST'
    country = '爱沙尼亚'
    language = 'et'
    source_timezone = 'Europe/Tallinn'
    start_date = '2024-01-01'
    use_curl_cffi = True

    allowed_domains = ["www.emta.ee", "search.service.eu-live.vportal.ee"]
    # Internal JSON API endpoint for search/news
    api_url = "https://search.service.eu-live.vportal.ee/v1/search/emta?filters%5Btype%5D=Uudis&sort_by=created&page={page}&langcode=et&limit=15"

    fallback_content_selector = "article.node, main.w-100, .field--name-body"

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "news_scraper.middlewares.CurlCffiMiddleware": 543,
            "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
        },
        "CURLL_CFFI_IMPERSONATE": "chrome120",
        "CONCURRENT_REQUESTS": 8,
        "DOWNLOAD_DELAY": 0.5
    }

    def start_requests(self):
        # Start with page 1
        yield scrapy.Request(
            self.api_url.format(page=1),
            callback=self.parse_json,
            headers={
                "Referer": "https://www.emta.ee/",
                "Origin": "https://www.emta.ee"
            },
            meta={"page": 1},
            dont_filter=True
        )

    def parse_json(self, response):
        """
        Parse JSON response from EMTA's backend search service.
        Uses SmartSpider's should_process for incremental filtering.
        """
        try:
            data = json.loads(response.text)
        except Exception as e:
            self.logger.error(f"JSON Parse Error: {e}")
            return

        docs = data.get("response", {}).get("docs", [])
        if not docs:
            self.logger.info(f"No documents found on page {response.meta['page']}")
            return

        has_valid_item_in_window = False

        for doc in docs:
            title = doc.get("title") or doc.get("label")
            uri = doc.get("uri")
            created_iso = doc.get("created")  # Format: 2026-03-31T05:10:24Z

            if not title or not uri:
                continue

            # Build full URL
            full_url = "https://www.emta.ee" + uri if not uri.startswith("http") else uri

            # Parse date from JSON
            publish_time = self.parse_date(created_iso) if created_iso else None

            # SmartSpider incremental filtering
            if not self.should_process(full_url, publish_time):
                continue

            has_valid_item_in_window = True

            # Request detail page for full body content
            yield scrapy.Request(
                full_url,
                callback=self.parse_article,
                meta={
                    "title_hint": title,
                    "publish_time_hint": publish_time,
                },
            )

        # Pagination: stop when no valid items in window or no more docs
        current_page = response.meta["page"]
        if has_valid_item_in_window and len(docs) > 0:
            yield scrapy.Request(
                self.api_url.format(page=current_page + 1),
                callback=self.parse_json,
                headers={
                    "Referer": "https://www.emta.ee/",
                    "Origin": "https://www.emta.ee"
                },
                meta={"page": current_page + 1},
                dont_filter=True
            )

    def parse_article(self, response):
        """
        Extract full content from the news detail page using SmartSpider auto_parse_item.
        Falls back to manual content extraction if ContentEngine returns nothing.
        """
        item = self.auto_parse_item(
            response,
            title_xpath=None,
            publish_time_xpath=None,
        )

        # Fallback: manual content extraction if ContentEngine found nothing
        if not item.get('content_plain'):
            lead = response.css('.field--name-field-lead-text p::text, .field--name-field-summary p::text').get() or ""
            body_nodes = response.css('.field--name-body p::text, .field--name-body li::text').getall()
            body = "\n".join([b.strip() for b in body_nodes if b.strip()])
            content = (lead + "\n\n" + body).strip()

            if not content:
                body_nodes = response.css('article p::text').getall()
                content = "\n".join([b.strip() for b in body_nodes if b.strip()])

            if content:
                item['content_plain'] = content
                item['content_html'] = None

        item['author'] = "Maksu- ja Tolliamet (EMTA)"
        item['section'] = "News"

        yield item
