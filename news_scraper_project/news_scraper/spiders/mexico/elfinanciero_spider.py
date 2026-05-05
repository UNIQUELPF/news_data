import scrapy
from news_scraper.spiders.smart_spider import SmartSpider


class MexicoElFinancieroSpider(SmartSpider):
    name = 'mexico_elfinanciero'
    country_code = 'MEX'
    country = '墨西哥'
    language = 'es'
    source_timezone = 'America/Mexico_City'
    allowed_domains = ['elfinanciero.com.mx']
    start_urls = ['https://www.elfinanciero.com.mx/economia/']
    fallback_content_selector = '.c-content-body'
    strict_date_required = False
    MAX_PAGES = 80

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
        articles = response.css('.b-results-list a.c-link::attr(href)').getall()
        if not articles:
            articles = response.css('a.c-link::attr(href)').getall()

        has_valid_item_in_window = False

        for link in articles:
            if '/202' not in link:
                continue
            full_url = response.urljoin(link)
            if self.should_process(full_url):
                has_valid_item_in_window = True
                yield scrapy.Request(full_url, callback=self.parse_article)

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
            title_xpath="//h1/text()",
            publish_time_xpath="//time[@class='c-date']/@dateTime",
        )
        item['author'] = response.css('.c-attribution a::text').get() or 'El Financiero'
        item['section'] = 'Economía'

        if item.get('content_plain') and len(item['content_plain']) > 200:
            yield item
