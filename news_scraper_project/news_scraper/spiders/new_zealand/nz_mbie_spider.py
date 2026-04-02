import scrapy
from datetime import datetime
import re
from news_scraper.spiders.base_spider import BaseNewsSpider

class NzMbieSpider(BaseNewsSpider):
    name = "nz_mbie"
    allowed_domains = ["mbie.govt.nz"]
    start_url_tmpl = "https://www.mbie.govt.nz/about/news?start={}"
    
    use_curl_cffi = True
    
    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "news_scraper.middlewares.CurlCffiMiddleware": 543,
            "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
        },
        "CURLL_CFFI_IMPERSONATE": "chrome120",
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1
    }
    
    target_table = "nz_mbie_news"

    def start_requests(self):
        yield scrapy.Request(self.start_url_tmpl.format(0), meta={'start': 0})

    def parse(self, response):
        links = response.css('a.listing-link.f4::attr(href)').getall()
        start = response.meta.get('start', 0)
        self.logger.info(f"Listing Page: Found {len(links)} links at start={start}")
        
        for link in links:
            yield response.follow(link, self.parse_article)
            
        if links:
            next_start = start + 10
            yield scrapy.Request(self.start_url_tmpl.format(next_start), callback=self.parse, meta={'start': next_start})

    def parse_article(self, response):
        pub_date = None
        date_text = response.xpath("//p[contains(text(), 'Published:')]/text()").get()
        if date_text:
            date_match = re.search(r'Published:\s*(.*)', date_text, re.IGNORECASE)
            if date_match:
                try:
                    pub_date = datetime.strptime(date_match.group(1).strip(), '%d %B %Y')
                except Exception:
                    pass

        if pub_date and not self.filter_date(pub_date):
            return

        title = response.css('h1.content-page-heading::text').get("").strip()
        intro = response.css('p.page-intro::text').get("").strip()
        body_parts = response.css('div.content-area p::text, div.content-area li::text').getall()
        main_content = "\n\n".join([p.strip() for p in body_parts if len(p.strip()) > 15])
        
        full_content = (intro + "\n\n" + main_content).strip() if intro else main_content

        if full_content:
            yield {
                "url": response.url,
                "title": title,
                "content": full_content,
                "publish_time": pub_date,
                "author": "New Zealand MBIE",
                "language": "en",
                "section": "News"
            }
