import scrapy
from datetime import datetime
from news_scraper.spiders.base_spider import BaseNewsSpider

class Bg24chasaSpider(BaseNewsSpider):
    name = "bg_24chasa"
    allowed_domains = ["www.24chasa.bg"]
    # Category 11764989 belongs to Business/Economy
    start_urls = ["https://www.24chasa.bg/biznes/11764989?page=1"]
    target_table = "bg_24chasa_news"

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "news_scraper.middlewares.CurlCffiMiddleware": 543,
            "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
        },
        "CURLL_CFFI_IMPERSONATE": "chrome120",
        "CONCURRENT_REQUESTS": 4, # Reduced for Playwright stability
        "DOWNLOAD_DELAY": 0.8
    }

    use_curl_cffi = True

    def parse(self, response):
        """
        Parse listing page: https://www.24chasa.bg/biznes/11764989?page=1
        """
        # Select all unique business article links
        links = response.css('a[href*="/biznes/article/"]::attr(href)').getall()
        # Deduplicate on the fly
        unique_links = list(set(links))
        
        found_any = False
        for link in unique_links:
            if not link.startswith('http'):
                link = "https://www.24chasa.bg" + link

            # Persistent memory fingerprint check
            if link in self.scraped_urls:
                continue
            
            found_any = True
            yield scrapy.Request(
                link, 
                callback=self.parse_article,
                # Enable Playwright for detailed content rendering as it's a heavy portal
                meta={"playwright": True} 
            )

        # Pagination
        if found_any:
            current_page = 1
            if 'page=' in response.url:
                try:
                    current_page = int(response.url.split('page=')[-1])
                except ValueError:
                    pass
            
            if current_page < 50: 
                next_page_url = f"https://www.24chasa.bg/biznes/11764989?page={current_page + 1}"
                yield scrapy.Request(next_page_url, callback=self.parse)

    def parse_article(self, response):
        # Title extraction from rendered DOM
        title = response.css('h1::text').get()
        if not title:
            title = response.css('title::text').get()
        
        # Date processing (Bulgarian: 02.04.2026 12:08)
        # Using specific time.date selector identified in audit
        date_str = response.css('time.date::text').get()
        pub_date = None
        if date_str:
            try:
                # DD.MM.YYYY HH:MM
                pub_date = datetime.strptime(date_str.strip(), "%d.%m.%Y %H:%M")
            except Exception as e:
                self.logger.warning(f"Could not parse Bulgarian date '{date_str}': {e}")

        # Date filtering (default 2026-01-01)
        if pub_date and not self.filter_date(pub_date):
            return

        # Content extraction from .article-content wrapper
        content_nodes = response.css('.article-content p::text, .article-content li::text').getall()
        content = "\n".join([c.strip() for c in content_nodes if c.strip()])

        if not content:
             content_nodes = response.css('article p::text').getall()
             content = "\n".join([c.strip() for c in content_nodes if c.strip()])

        if title and content:
            yield {
                "url": response.url,
                "title": title.strip(),
                "content": content,
                "publish_time": pub_date,
                "author": "24 Chasa Bulgaria",
                "language": "bg",
                "section": "Business"
            }
