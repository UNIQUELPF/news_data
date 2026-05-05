import scrapy
from news_scraper.spiders.smart_spider import SmartSpider


class NigeriaBusinessDaySpider(SmartSpider):
    name = 'ng_businessday'
    country_code = 'NGA'
    country = '尼日利亚'
    language = 'en'
    source_timezone = 'Africa/Lagos'
    start_date = '2024-01-01'
    allowed_domains = ['businessday.ng']
    fallback_content_selector = '.entry-content'

    strict_date_required = False

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.2,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 4,
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        }
    }

    def start_requests(self):
        yield scrapy.Request(
            'https://businessday.ng/category/business-economy/',
            callback=self.parse_list,
            meta={'page': 1}
        )

    def parse_list(self, response):
        articles = response.css('h3.entry-title a::attr(href)').getall() or \
                   response.css('.post-title a::attr(href)').getall()

        has_valid_item_in_window = False
        for link in articles:
            full_url = response.urljoin(link)
            if '/news/' in full_url or '/business-economy/' in full_url:
                if self.should_process(full_url):
                    has_valid_item_in_window = True
                    yield scrapy.Request(full_url, callback=self.parse_article)

        if has_valid_item_in_window:
            page = response.meta.get('page', 1)
            next_page = page + 1
            next_url = f"https://businessday.ng/category/business-economy/page/{next_page}/"
            yield scrapy.Request(
                next_url,
                callback=self.parse_list,
                meta={'page': next_page},
                dont_filter=True
            )

    def parse_article(self, response):
        item = self.auto_parse_item(
            response,
            title_xpath="//h1/text()",
            publish_time_xpath="//meta[@property='article:published_time']/@content",
        )
        item['author'] = response.css('.author-name::text').get() or 'BusinessDay Nigeria'
        item['section'] = 'Business & Economy'

        if not self.should_process(response.url, item.get('publish_time')):
            return

        if item.get('content_plain') and len(item['content_plain']) > 50:
            yield item
