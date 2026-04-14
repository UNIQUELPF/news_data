import scrapy
from datetime import datetime
from news_scraper.spiders.base_spider import BaseNewsSpider

class UkMoneyweekSpider(BaseNewsSpider):
    name = "uk_moneyweek"

    country_code = 'GBR'

    country = '英国'
    allowed_domains = ["moneyweek.com"]
    start_urls = ["https://moneyweek.com/economy/uk-economy"]
    
    target_table = "uk_moneyweek_news"

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "news_scraper.middlewares.CurlCffiMiddleware": 543,
            "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
        },
        "CURLL_CFFI_IMPERSONATE": "chrome120",
        "CONCURRENT_REQUESTS": 4,
        "DOWNLOAD_DELAY": 1
    }

    use_curl_cffi = True

    def parse(self, response):
        # 1. Parse article links from listing
        article_links = response.css('a.listing__link::attr(href), h2.listing__title a::attr(href)').getall()
        for link in list(set(article_links)):
            yield response.follow(link, self.parse_article)

        # 2. Pagination
        next_page = response.css('div.flexi-pagination a::attr(href)').getall()
        # Find the next page link - usually ordered 1, 2, 3... check current page index?
        # Actually images show simple numbered pages. We can follow them all or extract page count.
        for page in next_page:
            yield response.follow(page, self.parse)

    def parse_article(self, response):
        # Title
        title = response.css('h1.header__title::text').get("").strip()
        if not title:
            title = response.css('h1::text').get("").strip()

        # Date from meta
        date_meta = response.css('meta[property="article:published_time"]::attr(content)').get()
        pub_date = None
        if date_meta:
            try:
                # 2026-03-19T17:01:14Z or 2026-03-18T13:25:59+00:00
                dt_str = date_meta.split('.')[0].replace('Z', '')
                if '+' in dt_str:
                    dt_str = dt_str.split('+')[0]
                pub_date = datetime.fromisoformat(dt_str)
            except Exception as e:
                self.logger.error(f"Date parse error: {e}")

        if pub_date and not self.filter_date(pub_date):
            return

        # Content
        content_parts = response.css('div.article__body p::text, div.article__body p *::text, div.article__body h2::text, div.article__body li::text').getall()
        cleaned_content = "\n\n".join([p.strip() for p in content_parts if p.strip()])

        if cleaned_content and title:
            yield {
                "url": response.url,
                "title": title,
                "content": cleaned_content,
                "publish_time": pub_date,
                "author": response.css('meta[name="author"]::attr(content)').get("MoneyWeek"),
                "language": "en",
                "section": "UK Economy"
            }
