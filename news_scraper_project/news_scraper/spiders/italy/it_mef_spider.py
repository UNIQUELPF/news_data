import scrapy
from datetime import datetime
import re
from news_scraper.spiders.base_spider import BaseNewsSpider

class ItMefSpider(BaseNewsSpider):
    name = "it_mef"
    allowed_domains = ["mef.gov.it"]
    # We use a base URL and increment pages manually in parse if needed, 
    # but starting with a few helps
    start_urls = ["https://www.mef.gov.it/en/ufficio-stampa/notizie.html"]
    
    target_table = "it_mef_news"

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "news_scraper.middlewares.CurlCffiMiddleware": 543,
            "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
        },
        "CURLL_CFFI_IMPERSONATE": "chrome120",
        "CONCURRENT_REQUESTS": 4,
        "DOWNLOAD_DELAY": 0.5
    }

    use_curl_cffi = True

    def parse(self, response):
        # Precise news links from the list
        links = response.css('a[href*="/en/inevidenza/"]::attr(href)').getall()
        links = [l for l in links if not l.endswith('.html')] # exclude list page itself
        
        for link in list(set(links)):
            yield response.follow(link, self.parse_article)

        # Pagination logic
        next_page = response.css('a[aria-label^="Go to page"], a.page-link-precsucc::attr(href)').getall()
        for np in next_page:
            if 'page=' in np:
                yield response.follow(np, self.parse)

    def parse_article(self, response):
        # The true title is often h2.fContent or inside a specific main header
        title = response.css('h2.fContent::text, h2#fContent::text, h1.fContent::text').get("").strip()
        if not title:
            title = response.css('title::text').get("").strip().replace(' - Ministero dell\'Economia e delle Finanze', '')

        # Deep text extraction for date
        # It contains <i class="bi bi-calendar-event me-2"></i>&nbsp;January 12, 2026
        date_parts = response.css('small.text-date *::text').getall()
        date_combined = " ".join(date_parts).strip()
        
        pub_date = None
        if date_combined:
            try:
                # Capture pattern like "January 12, 2026"
                match = re.search(r'([A-Z][a-z]+ \d{1,2}, \d{4})', date_combined)
                if match:
                    clean_date = match.group(1)
                    pub_date = datetime.strptime(clean_date, "%B %d, %Y")
            except Exception as e:
                self.logger.error(f"Final regex parsing failed for {date_combined}: {e}")

        if pub_date and not self.filter_date(pub_date):
            return

        content_parts = response.css('div#pageContent p::text, div#pageContent div::text, div#pageContent li::text').getall()
        # Clean up tags and extra spaces
        cleaned_content = "\n\n".join([p.strip() for p in content_parts if len(p.strip()) > 10])

        if cleaned_content:
            yield {
                "url": response.url,
                "title": title,
                "content": cleaned_content,
                "publish_time": pub_date,
                "author": "Ministero dell'Economia e delle Finanze",
                "language": "en",
                "section": "Ufficio Stampa"
            }
