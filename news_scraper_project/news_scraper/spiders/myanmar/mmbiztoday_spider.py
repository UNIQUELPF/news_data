import scrapy
from news_scraper.spiders.smart_spider import SmartSpider


class MyanmarBizTodaySpider(SmartSpider):
    name = 'mm_mmbiztoday'
    country_code = 'MMR'
    country = '缅甸'
    language = 'en'
    source_timezone = 'Asia/Yangon'
    allowed_domains = ['mmbiztoday.com']
    start_urls = ['https://mmbiztoday.com/category/investment-and-finance/']
    fallback_content_selector = '.td-post-content'
    strict_date_required = False
    MAX_PAGES = 30

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.0,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 4,
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        }
    }

    def start_requests(self):
        yield scrapy.Request(
            self.start_urls[0],
            callback=self.parse_list,
            meta={'page': 1}
        )

    def parse_list(self, response):
        articles = response.css('.td-module-title h3 a::attr(href)').getall()
        if not articles:
            articles = response.css('h3.entry-title a::attr(href)').getall()

        has_valid_item_in_window = False

        for link in articles:
            if not link or not link.startswith('http'):
                continue
            if self.should_process(link):
                has_valid_item_in_window = True
                yield scrapy.Request(link, callback=self.parse_article)

        current_page = response.meta.get('page', 1)
        if has_valid_item_in_window and current_page < self.MAX_PAGES:
            next_page = current_page + 1
            next_url = f"{self.start_urls[0]}page/{next_page}/"
            yield scrapy.Request(
                next_url,
                callback=self.parse_list,
                meta={'page': next_page},
                dont_filter=True
            )

    def parse_article(self, response):
        item = self.auto_parse_item(
            response,
            title_xpath="//h1[@class='entry-title']/text()",
            publish_time_xpath="//meta[@property='article:published_time']/@content",
        )
        item['author'] = response.css('.td-post-author-name a::text').get() or 'Myanmar Business Today'
        item['section'] = 'Investment & Finance'

        if item.get('content_plain') and len(item['content_plain']) > 150:
            yield item
