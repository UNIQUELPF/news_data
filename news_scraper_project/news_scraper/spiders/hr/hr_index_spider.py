import scrapy
import re
from datetime import datetime
from scrapy_playwright.page import PageMethod
from news_scraper.spiders.base_spider import BaseNewsSpider

class HrIndexSpider(BaseNewsSpider):
    name = "hr_index"

    country_code = 'HRV'

    country = '克罗地亚'
    allowed_domains = ["www.index.hr"]
    start_urls = ["https://www.index.hr/vijesti/rubrika/hrvatska/22.aspx"]
    target_table = "hr_index_news"

    # Croatian months mapping (genitive case)
    MONTHS_HR = {
        "siječnja": 1,
        "veljače": 2,
        "ožujka": 3,
        "travnja": 4,
        "svibnja": 5,
        "lipnja": 6,
        "srpnja": 7,
        "kolovoza": 8,
        "rujna": 9,
        "listopada": 10,
        "studenoga": 11,
        "prosinca": 12
    }

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "news_scraper.middlewares.CurlCffiMiddleware": 543,
            "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
        },
        "CURLL_CFFI_IMPERSONATE": "chrome120",
        "CONCURRENT_REQUESTS": 4, 
        "DOWNLOAD_DELAY": 1.0,
        "PLAYWRIGHT_LAUNCH_OPTIONS": {"headless": True}
    }

    use_curl_cffi = True

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(
                url, 
                callback=self.parse,
                meta={
                    "playwright": True,
                    "playwright_page_methods": [
                        PageMethod("wait_for_selector", "a.vijesti-text-hover", timeout=15000),
                    ]
                }
            )

    def parse(self, response):
        """
        Parse listing page with 'Load More' logic
        """
        anchors = response.css('a.vijesti-text-hover')
        found_any = False
        
        for a in anchors:
            link = a.css('::attr(href)').get()
            if not link: continue
            
            if not link.startswith('http'):
                link = "https://www.index.hr" + link

            if link in self.scraped_urls:
                continue

            found_any = True
            yield scrapy.Request(
                link, 
                callback=self.parse_article,
                meta={
                    "playwright": True,
                    "playwright_page_methods": [
                        PageMethod("wait_for_selector", "h1", timeout=10000),
                    ]
                }
            )

        # 'Load More' Pagination
        # If we didn't hit duplicates, we keep loading
        if found_any:
            yield scrapy.Request(
                response.url,
                callback=self.parse,
                meta={
                    "playwright": True,
                    "playwright_page_methods": [
                        PageMethod("click", ".btn-read-more"),
                        PageMethod("wait_for_timeout", 3000),
                        PageMethod("wait_for_selector", "a.vijesti-text-hover"),
                    ]
                },
                dont_filter=True
            )

    def parse_article(self, response):
        title = response.css('h1::text').get()
        if not title:
             title = response.css('title::text').get()
        
        # publish-date format: HH:mm, DD. month_name YYYY.
        date_str = response.css('.publish-date::text').get()
        pub_date = None
        if date_str:
            try:
                # 17:45, 06. travnja 2026.
                match = re.search(r'(\d{2}:\d{2}), (\d{2})\. (\w+) (\d{4})\.', date_str)
                if match:
                    time_part = match.group(1)
                    day_part = int(match.group(2))
                    month_name = match.group(3).lower()
                    year_part = int(match.group(4))
                    
                    month_part = self.MONTHS_HR.get(month_name)
                    if month_part:
                        pub_date = datetime(year_part, month_part, day_part, 
                                            int(time_part.split(':')[0]), 
                                            int(time_part.split(':')[1]))
            except Exception:
                 self.logger.warning(f"Date parse failed for: {date_str}")

        if pub_date and not self.filter_date(pub_date):
            return

        # Body: .text container
        content_nodes = response.css('.text p::text, .text div::text').getall()
        content = "\n".join([c.strip() for c in content_nodes if len(c.strip()) > 30])

        if title and len(content) > 100:
            yield {
                "url": response.url,
                "title": title.strip(),
                "content": content,
                "publish_time": pub_date,
                "author": "Index.hr",
                "language": "hr",
                "section": "News"
            }
