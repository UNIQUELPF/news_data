import scrapy
from datetime import datetime
from scrapy_playwright.page import PageMethod
from news_scraper.spiders.base_spider import BaseNewsSpider

class ItIlsole24oreSpider(BaseNewsSpider):
    name = "it_ilsole24ore"
    allowed_domains = ["ilsole24ore.com"]
    
    start_urls = [
        "https://www.ilsole24ore.com/sez/economia/fondi-ue",
        "https://www.ilsole24ore.com/sez/economia/industria",
        "https://www.ilsole24ore.com/sez/economia/energia-e-ambiente"
    ]
    
    target_table = "it_ilsole24ore_news"

    custom_settings = {
        "DOWNLOAD_HANDLERS": {
            "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        },
        "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
        "PLAYWRIGHT_BROWSER_TYPE": "chromium",
        "PLAYWRIGHT_LAUNCH_OPTIONS": {"headless": True, "timeout": 60000},
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 60000 * 5,
        "CONCURRENT_REQUESTS": 2, 
        "DOWNLOAD_DELAY": 1
    }

    def start_requests(self):
        js_scroll = """
        async () => {
            // Remove overlays
            let cb = document.querySelector('#iubenda-cs-banner');
            if(cb) cb.remove();
            let nora = document.querySelector('.onesignal-customlink-container');
            if(nora) nora.remove();
            
            let targetDate = new Date('2026-01-01');
            // Try to click the Mostra altri button up to 50 times
            for(let i = 0; i < 50; i++) {
                let times = document.querySelectorAll('time[datetime]');
                if(times.length > 0) {
                    let lastTimeEl = times[times.length - 1];
                    let dateStr = lastTimeEl.getAttribute('datetime');
                    if(dateStr && new Date(dateStr) < targetDate) {
                        break;
                    }
                }
                let btn = document.querySelector('.btn--collapse');
                if(btn) {
                    btn.click();
                    await new Promise(r => setTimeout(r, 2000));
                } else {
                    break;
                }
            }
        }
        """
        for url in self.start_urls:
            yield scrapy.Request(
                url,
                meta={
                    "playwright": True,
                    "playwright_page_methods": [
                        PageMethod("wait_for_load_state", "domcontentloaded"),
                        PageMethod("evaluate", js_scroll),
                        PageMethod("wait_for_timeout", 2000),
                    ]
                },
                callback=self.parse
            )

    def parse(self, response):
        article_links = response.css('a[href^="/art/"]::attr(href)').getall()
        article_links = list(set(article_links))
        
        self.logger.info(f"Listing Page {response.url}: Found {len(article_links)} total links after expansion.")
        
        for link in article_links:
            if '/art/' not in link and '/video/' not in link:
                continue
                
            abs_url = response.urljoin(link)
            yield scrapy.Request(
                abs_url,
                meta={
                    "playwright": True,
                    "playwright_page_methods": [
                        PageMethod("wait_for_load_state", "domcontentloaded"),
                    ]
                },
                callback=self.parse_article
            )

    def parse_article(self, response):
        title = response.css('h1.atitle::text').get("").strip()
        if not title:
            title = response.css('title::text').get("").strip()
            
        date_raw = response.css('time[datetime]::attr(datetime)').get()
        pub_date = None
        if date_raw:
            try:
                if date_raw.endswith('Z'):
                    date_raw = date_raw[:-1]
                pub_date = datetime.fromisoformat(date_raw.split('+')[0])
            except Exception as e:
                self.logger.error(f"Date error: {e} for {date_raw}")
        
        if not self.filter_date(pub_date):
            return

        content_parts = response.css('div.atxt p::text, div.atxt p *::text').getall()
        if not content_parts:
            content_parts = response.css('article p::text, article p *::text').getall()
            
        cleaned_content = "\n\n".join([p.strip() for p in content_parts if len(p.strip()) > 10])

        if cleaned_content:
            yield {
                "url": response.url,
                "title": title,
                "content": cleaned_content,
                "publish_time": pub_date,
                "author": "Il Sole 24 Ore",
                "language": "it",
                "section": "Economia"
            }
