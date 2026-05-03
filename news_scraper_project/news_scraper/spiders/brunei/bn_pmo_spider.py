import scrapy
from news_scraper.spiders.smart_spider import SmartSpider

class BnPmoSpider(SmartSpider):
    name = 'bn_pmo'

    country_code = 'BRN'
    country = '文莱'
    language = 'en'
    source_timezone = 'Asia/Brunei'
    use_curl_cffi = True

    allowed_domains = ['pmo.gov.bn']

    base_url = 'https://www.pmo.gov.bn/1149-2/page/{}/?et_blog'

    fallback_content_selector = ".entry-content .et_builder_inner_content"

    custom_settings = {
        'DOWNLOAD_DELAY': 1.0,
        'DOWNLOAD_TIMEOUT': 30,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 2,
    }

    def start_requests(self):
        yield scrapy.Request(
            self.base_url.format(1),
            callback=self.parse_list,
            meta={'page': 1},
            dont_filter=True
        )

    def parse_list(self, response):
        articles = response.css('article.et_pb_post')

        has_valid_item_in_window = False

        for article in articles:
            url = article.css('.entry-title a::attr(href)').get()
            if not url:
                continue
            url = response.urljoin(url)

            title_hint = article.css('.entry-title a::text').get()

            date_str = article.css('.published::text').get()
            publish_time = self.parse_date(date_str.strip()) if date_str else None

            if not self.should_process(url, publish_time):
                continue

            has_valid_item_in_window = True
            yield scrapy.Request(
                url,
                callback=self.parse_detail,
                meta={
                    'title_hint': title_hint,
                    'publish_time_hint': publish_time,
                    'section_hint': 'Messages',
                }
            )

        if has_valid_item_in_window:
            next_page = response.meta['page'] + 1
            yield scrapy.Request(
                self.base_url.format(next_page),
                callback=self.parse_list,
                meta={'page': next_page},
                dont_filter=True
            )

    def parse_detail(self, response):
        item = self.auto_parse_item(
            response,
            title_xpath="//h1[contains(@class,'title')]//text()",
            publish_time_xpath="//span[contains(@class,'published')]//text() | //meta[@property='article:published_time']/@content",
        )

        item['author'] = "Prime Minister's Office Brunei"
        item['section'] = response.meta.get('section_hint', 'Messages')

        yield item
