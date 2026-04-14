import scrapy
from datetime import datetime
from news_scraper.spiders.base_spider import BaseNewsSpider

class BaCapitalSpider(BaseNewsSpider):
    name = "ba_capital"

    country_code = 'BIH'

    country = '波黑'
    allowed_domains = ["capital.ba"]
    # Financial/Economy section link provided by user
    start_urls = ["https://capital.ba/category/privreda/"]
    target_table = "ba_capital_news"

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "news_scraper.middlewares.CurlCffiMiddleware": 543,
            "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
        },
        "CURLL_CFFI_IMPERSONATE": "chrome120",
        "CONCURRENT_REQUESTS": 4, # Throttled for stability
        "DOWNLOAD_DELAY": 0.8
    }

    use_curl_cffi = True

    def parse(self, response):
        """
        Parse listing page: https://capital.ba/category/privreda/
        """
        # Select article boxes
        articles = response.css('article.l-post')
        found_any = False
        
        for art in articles:
            # ISO Datetime attribute is highly reliable
            iso_date = art.css('time.post-date::attr(datetime)').get()
            link = art.css('.post-title a::attr(href)').get()
            
            if not link:
                continue
            
            # Persistent memory fingerprint check
            if link in self.scraped_urls:
                continue

            pub_date = None
            if iso_date:
                try:
                    # ISO Format: 2026-02-24T14:31:54+02:00
                    pub_date = datetime.fromisoformat(iso_date)
                except Exception as e:
                    self.logger.warning(f"ISO Date parse error: {e}")

            # Date filtering (default 2026-01-01)
            if pub_date and not self.filter_date(pub_date):
                continue

            found_any = True
            yield scrapy.Request(
                link, 
                callback=self.parse_article,
                meta={"publish_time": pub_date, "playwright": True}
            )

        # Pagination logic: /page/X/
        if found_any:
            current_page = 1
            if '/page/' in response.url:
                try:
                    current_page = int(response.url.split('/page/')[-1].strip('/'))
                except ValueError:
                    pass
            
            # Recurse to next page
            if current_page < 100: # Exploratory safety cap
                next_page_url = f"https://capital.ba/category/privreda/page/{current_page + 1}/"
                yield scrapy.Request(next_page_url, callback=self.parse)

    def parse_article(self, response):
        # Extract title from rendered H1
        title = response.css('h1.is-title.post-title::text').get()
        if not title:
            title = response.css('title::text').get()
        
        # Extract author
        author = response.css('.meta-item.author a::text').get() or "Capital.ba Staff"
        
        # Content extraction from .post-content wrapper
        content_nodes = response.css('.post-content.entry-content p::text, .post-content.entry-content li::text').getall()
        content = "\n".join([c.strip() for c in content_nodes if c.strip()])

        if title and content:
            yield {
                "url": response.url,
                "title": title.strip(),
                "content": content,
                "publish_time": response.meta["publish_time"],
                "author": author.strip(),
                "language": "bs",
                "section": "Economy"
            }
        elif title:
            # Fallback for different layouts
            body_nodes = response.css('article p::text').getall()
            content = "\n".join([b.strip() for b in body_nodes if b.strip()])
            if content:
                yield {
                    "url": response.url,
                    "title": title.strip(),
                    "content": content,
                    "publish_time": response.meta["publish_time"],
                    "author": author.strip(),
                    "language": "bs",
                    "section": "Economy"
                }
