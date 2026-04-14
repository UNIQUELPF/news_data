import scrapy
import json
from datetime import datetime
from news_scraper.spiders.base_spider import BaseNewsSpider

class EeEmtaSpider(BaseNewsSpider):
    name = "ee_emta"

    country_code = 'EST'

    country = '爱沙尼亚'
    allowed_domains = ["www.emta.ee", "search.service.eu-live.vportal.ee"]
    # Internal JSON API endpoint for search/news
    api_url = "https://search.service.eu-live.vportal.ee/v1/search/emta?filters%5Btype%5D=Uudis&sort_by=created&page={page}&langcode=et&limit=15"
    target_table = "ee_emta_news"

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "news_scraper.middlewares.CurlCffiMiddleware": 543,
            "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
        },
        "CURLL_CFFI_IMPERSONATE": "chrome120",
        "CONCURRENT_REQUESTS": 8,
        "DOWNLOAD_DELAY": 0.5
    }

    use_curl_cffi = True

    def start_requests(self):
        # Start with page 1 as verified by subagent
        yield scrapy.Request(
            self.api_url.format(page=1),
            callback=self.parse_json,
            headers={
                "Referer": "https://www.emta.ee/",
                "Origin": "https://www.emta.ee"
            },
            meta={"page": 1}
        )

    def parse_json(self, response):
        """
        Parse JSON response from EMTA's backend search service.
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

        for doc in docs:
            # Fields identified in audit
            title = doc.get("title") or doc.get("label")
            uri = doc.get("uri")
            created_iso = doc.get("created") # Format: 2026-03-31T05:10:24Z
            
            if not title or not uri:
                continue

            # Build full URL
            full_url = "https://www.emta.ee" + uri if not uri.startswith("http") else uri
            
            # Memory fingerprinting for incremental check
            if full_url in self.scraped_urls:
                continue

            # Parse date for filtering
            pub_date = None
            if created_iso:
                try:
                    # ISO 8601: 2026-03-31T05:10:24Z
                    pub_date = datetime.fromisoformat(created_iso.replace('Z', '+00:00'))
                except Exception as e:
                    self.logger.warning(f"Date Parse Error: {e}")

            # Date filtering (2026-01-01)
            if pub_date and not self.filter_date(pub_date):
                continue

            # Request detail page for full body content
            yield scrapy.Request(
                full_url,
                callback=self.parse_article,
                meta={"title": title, "publish_time": pub_date},
                # Detail pages also use Drupal/Angular context, use Playwright to be safe
                # but let's try direct curl_cffi first as it's faster.
                # If body fails, I'll add Playwright here later.
            )

        # Pagination
        current_page = response.meta["page"]
        if current_page < 50: # Safety limit
            yield scrapy.Request(
                self.api_url.format(page=current_page + 1),
                callback=self.parse_json,
                headers={
                    "Referer": "https://www.emta.ee/",
                    "Origin": "https://www.emta.ee"
                },
                meta={"page": current_page + 1}
            )

    def parse_article(self, response):
        """
        Extract full content from the news detail page.
        """
        # Selectors confirmed by subagent
        lead = response.css('.field--name-field-lead-text p::text, .field--name-field-summary p::text').get() or ""
        body_nodes = response.css('.field--name-body p::text, .field--name-body li::text').getall()
        body = "\n".join([b.strip() for b in body_nodes if b.strip()])
        
        content = (lead + "\n\n" + body).strip()
        
        # Fallback if content is empty (site might be using a different template)
        if not content:
            body_nodes = response.css('article p::text').getall()
            content = "\n".join([b.strip() for b in body_nodes if b.strip()])

        if content:
            yield {
                "url": response.url,
                "title": response.meta["title"],
                "content": content,
                "publish_time": response.meta["publish_time"],
                "author": "Maksu- ja Tolliamet (EMTA)",
                "language": "et",
                "section": "News"
            }
