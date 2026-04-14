import scrapy
import re
from datetime import datetime
from news_scraper.spiders.base_spider import BaseNewsSpider

class ItBorseSpider(BaseNewsSpider):
    name = "it_borse"

    country_code = 'ITA'

    country = '意大利'
    allowed_domains = ["borse.it"]
    start_urls = ["https://www.borse.it/notizie"]
    
    target_table = "it_borse_news"

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "news_scraper.middlewares.CurlCffiMiddleware": 543,
            "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
        },
        "CURLL_CFFI_IMPERSONATE": "chrome120",
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 0.5
    }

    use_curl_cffi = True

    month_map = {
        'gennaio': '01', 'febbraio': '02', 'marzo': '03', 'aprile': '04',
        'maggio': '05', 'giugno': '06', 'luglio': '07', 'agosto': '08',
        'settembre': '09', 'ottobre': '10', 'novembre': '11', 'dicembre': '12'
    }

    def parse(self, response):
        article_links = response.css('a.card-post__title::attr(href)').getall()
        for link in article_links:
            yield response.follow(link, callback=self.parse_article)
            
        next_page = response.css('a.next.page-numbers::attr(href)').get()
        if next_page:
            yield response.follow(next_page, self.parse)

    def parse_article(self, response):
        title = response.css('h1::text').get("").strip()
        date_str = response.css('span.date::text').get("").strip()
        
        pub_date = None
        if date_str:
            try:
                parts = date_str.lower().split()
                if len(parts) >= 3:
                    day = int(parts[0])
                    month = int(self.month_map.get(parts[1], '01'))
                    year = int(parts[2])
                    pub_date = datetime(year, month, day)
            except Exception as e:
                self.logger.error(f"Failed to parse date: {date_str} - {e}")
                
        if pub_date and not self.filter_date(pub_date):
            return

        content_parts = response.css('article.single-post__article p::text, article.single-post__article p *::text').getall()
        if not content_parts:
            # fallback
            content_parts = response.css('div.post__content p::text, div.post__content p *::text').getall()

        cleaned_content = "\n\n".join([p.strip() for p in content_parts if len(p.strip()) > 10])

        if cleaned_content:
            yield {
                "url": response.url,
                "title": title,
                "content": cleaned_content,
                "publish_time": pub_date,
                "author": "Borse.it",
                "language": "it",
                "section": "Notizie"
            }
