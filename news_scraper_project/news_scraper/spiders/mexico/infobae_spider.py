import scrapy
from news_scraper.spiders.smart_spider import SmartSpider


class MexicoInfobaeSpider(SmartSpider):
    name = 'mexico_infobae'
    country_code = 'MEX'
    country = '墨西哥'
    language = 'es'
    source_timezone = 'America/Mexico_City'
    allowed_domains = ['infobae.com']
    start_urls = ['https://www.infobae.com/mexico/ultimas-noticias/']
    fallback_content_selector = '.article-body'
    strict_date_required = False
    MAX_PAGES = 200

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 0.8,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 8,
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        }
    }

    def start_requests(self):
        url = f"{self.start_urls[0]}?page=1"
        yield scrapy.Request(
            url,
            callback=self.parse_list,
            meta={'page': 1}
        )

    def parse_list(self, response):
        articles = response.css('a.feed-list-card::attr(href)').getall()
        if not articles:
            articles = response.css('.nd-feed-list-card a::attr(href)').getall()

        has_valid_item_in_window = False

        for link in articles:
            full_url = response.urljoin(link)
            if '/mexico/202' not in full_url:
                continue
            if self.should_process(full_url):
                has_valid_item_in_window = True
                yield scrapy.Request(full_url, callback=self.parse_article)

        current_page = response.meta.get('page', 1)
        if has_valid_item_in_window and current_page < self.MAX_PAGES:
            next_page = current_page + 1
            next_url = f"{self.start_urls[0]}?page={next_page}"
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
        item['author'] = response.css('.author-name::text').get() or 'Infobae Mexico'
        item['section'] = 'Ultimas Noticias'

        if item.get('content_plain') and len(item['content_plain']) > 200:
            yield item
