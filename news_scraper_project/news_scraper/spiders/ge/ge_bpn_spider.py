import scrapy
import json
import re
from datetime import datetime
from scrapy_playwright.page import PageMethod
from news_scraper.spiders.base_spider import BaseNewsSpider

class GeBpnSpider(BaseNewsSpider):
    name = "ge_bpn"
    allowed_domains = ["www.bpn.ge"]
    start_urls = ["https://www.bpn.ge/category/161-ekonomika/"]
    target_table = "ge_bpn_news"

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "news_scraper.middlewares.CurlCffiMiddleware": 543,
            "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
        },
        "CURLL_CFFI_IMPERSONATE": "chrome120",
        "CONCURRENT_REQUESTS": 2, 
        "DOWNLOAD_DELAY": 1.5,
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 120000,
        "PLAYWRIGHT_LAUNCH_OPTIONS": {
            "headless": True,
            "args": ["--disable-blink-features=AutomationControlled"]
        }
    }

    use_curl_cffi = True

    def parse(self, response):
        """
        List page: Static extraction for maximum reliability
        """
        links = []
        scripts = response.css('script[type="application/ld+json"]::text').getall()
        for s in scripts:
            try:
                data = json.loads(s)
                if isinstance(data, dict):
                    items = data.get('itemListElement', [])
                    for item in items:
                        url = item.get('item') or item.get('url')
                        if isinstance(url, str) and '/article/' in url:
                            links.append(url)
            except: pass

        if not links:
             links = re.findall(r'https://www\.bpn\.ge/article/[\w-]+/', response.text)

        links = list(set(links))
        self.logger.info(f"GE_BPN List Sync: Found {len(links)} links.")

        found_any = False
        for link in links:
            if link in self.scraped_urls:
                continue

            found_any = True
            yield scrapy.Request(
                link, 
                callback=self.parse_article,
                meta={
                    "playwright": True,
                    "playwright_page_methods": [
                        # Wait for DOM effectively without visibility constraints on hidden tags
                        PageMethod("wait_for_load_state", "domcontentloaded", timeout=90000),
                        PageMethod("wait_for_selector", ".article_body_wrapper", state="attached", timeout=60000),
                    ]
                }
            )

        # Pagination using ?page=X
        if found_any:
            current_page = 1
            if 'page=' in response.url:
                try:
                    match = re.search(r'page=(\d+)', response.url)
                    if match: current_page = int(match.group(1))
                except: pass
            
            if current_page < 120: 
                next_page_url = f"https://www.bpn.ge/category/161-ekonomika/?page={current_page + 1}"
                yield scrapy.Request(next_page_url, callback=self.parse)

    def parse_article(self, response):
        # Precise Ka-language business data aggregation
        title = response.css('meta[property="og:title"]::attr(content)').get()
        if not title:
             title = response.css('.article_title h1::text, h1::text').get()
        
        date_str = response.css('.article_date .date_time::text, .article_date::text').get()
        pub_date = None
        if date_str:
            try:
                match = re.search(r'(\d{2}\.\d{2}\.\d{4})', date_str)
                if match:
                     pub_date = datetime.strptime(match.group(0), "%d.%m.%Y")
            except: pass

        if pub_date and not self.filter_date(pub_date):
            return

        # Content from wrapper or OG fallback
        intro = response.css('meta[property="og:description"]::attr(content)').get() or ""
        body_nodes = response.css('.article_body_wrapper p::text, .article_body_wrapper div::text, .article_body_wrapper p span::text').getall()
        body = "\n".join([c.strip() for c in body_nodes if len(c.strip()) > 30])
        
        content = (intro + "\n" + body).strip()

        if title and len(content) > 50:
            yield {
                "url": response.url,
                "title": title.strip(),
                "content": content,
                "publish_time": pub_date,
                "author": "BPN.ge",
                "language": "ka",
                "section": "Economy"
            }
