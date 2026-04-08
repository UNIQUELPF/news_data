import scrapy
import re
from datetime import datetime
from scrapy_playwright.page import PageMethod
from news_scraper.spiders.base_spider import BaseNewsSpider

class CzPatriaSpider(BaseNewsSpider):
    name = "cz_patria"
    allowed_domains = ["www.patria.cz"]
    start_urls = ["https://www.patria.cz/zpravodajstvi/zpravy.html"]
    target_table = "cz_patria_news"

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "news_scraper.middlewares.CurlCffiMiddleware": 543,
            "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
        },
        "CURLL_CFFI_IMPERSONATE": "chrome120",
        "CONCURRENT_REQUESTS": 2, 
        "DOWNLOAD_DELAY": 1.5,
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
                        PageMethod("wait_for_selector", "a[href^='/zpravodajstvi/'][title]", timeout=15000),
                    ]
                }
            )

    def parse(self, response):
        """
        Parse listing page: https://www.patria.cz/zpravodajstvi/zpravy.html
        """
        # Select article items
        anchors = response.css('a[href^="/zpravodajstvi/"][title]')
        found_any = False
        
        for a in anchors:
            link = a.css('::attr(href)').get()
            if not link or '/69' not in link: # Articles usually have IDs like /6917645/
                continue
            
            if not link.startswith('http'):
                link = "https://www.patria.cz" + link

            # Date check in list: often preceding text or container
            # Fallback to detail page if list extraction is messy
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

        # Pagination logic: Clicking the Next pager
        # The screenshot shows <a class="goto" title="2" ...>
        # We find the 'active' page and click the one with title = active+1
        current_page_text = response.css('.pagenavigator span.active::text').get()
        if current_page_text and found_any:
            try:
                next_page_num = int(current_page_text) + 1
                next_selector = f'.pagenavigator a.goto[title="{next_page_num}"]'
                yield scrapy.Request(
                        response.url,
                        callback=self.parse,
                        meta={
                            "playwright": True,
                            "playwright_page_methods": [
                                PageMethod("click", next_selector),
                                PageMethod("wait_for_timeout", 3000), # Wait for AJAX
                                PageMethod("wait_for_selector", "a[href^='/zpravodajstvi/'][title]"),
                            ]
                        },
                        dont_filter=True # URL doesn't change, so we must disable filtering
                    )
            except ValueError:
                pass

    def parse_article(self, response):
        title = response.css('h1::text').get()
        if not title:
            title = response.css('title::text').get()
        
        # Publish time: Captured via text pattern DD.MM.YYYY HH:mm
        page_source = response.text
        date_match = re.search(r'(\d{2}\.\d{2}\.\d{4} \d{2}:\d{2})', page_source)
        pub_date = None
        if date_match:
            try:
                pub_date = datetime.strptime(date_match.group(1), "%d.%m.%Y %H:%M")
            except Exception:
                pass

        if pub_date and not self.filter_date(pub_date):
            return

        # Body in #ctl00_ctl00_ctl00_MC_Content_centerColumnPlaceHolder_Detail
        content_nodes = response.css('#ctl00_ctl00_ctl00_MC_Content_centerColumnPlaceHolder_Detail p::text, #ctl00_ctl00_ctl00_MC_Content_centerColumnPlaceHolder_Detail div::text').getall()
        content = "\n".join([c.strip() for c in content_nodes if len(c.strip()) > 30])

        if title and content:
            yield {
                "url": response.url,
                "title": title.strip(),
                "content": content,
                "publish_time": pub_date,
                "author": "Patria.cz",
                "language": "cs",
                "section": "News"
            }
