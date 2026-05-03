import scrapy
import re
from news_scraper.spiders.smart_spider import SmartSpider

class BnBrudirectSpider(SmartSpider):
    name = 'bn_brudirect'

    country_code = 'BRN'
    country = '文莱'
    language = 'en'
    source_timezone = 'Asia/Brunei'
    use_curl_cffi = True

    allowed_domains = ['brudirect.com']

    base_url = 'https://brudirect.com/result.php?title=&category=national-headline&subcategory=&p={}'

    fallback_content_selector = ".main-text"

    custom_settings = {
        'DOWNLOAD_DELAY': 2.0,
        'DOWNLOAD_TIMEOUT': 60,
        'RANDOMIZE_DOWNLOAD_DELAY': True,
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
        items = response.css('.category-page-post-item')

        has_valid_item_in_window = False

        for item in items:
            url = item.css('h3 a::attr(href)').get()
            if not url:
                continue
            url = response.urljoin(url)

            # Extract date from list page HTML (available for every article)
            date_str = item.css('.date a::text').get()
            publish_time = self.parse_date(date_str.strip()) if date_str else None

            if not self.should_process(url, publish_time):
                continue

            has_valid_item_in_window = True
            yield scrapy.Request(
                url,
                callback=self.parse_detail,
                meta={'title_hint': None, 'publish_time_hint': publish_time}
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
            title_xpath="//div[contains(@class,'page-top')]//h2/text()",
            publish_time_xpath="//div[contains(@class,'sub')]//a[contains(@href,'daywise.php?date=')]/text()",
        )

        # Featured photo is outside .main-text, prepend it to images
        featured_img = response.css('.featured-photo img::attr(src)').get()
        if featured_img:
            featured_url = response.urljoin(featured_img)
            images = item.get('images') or []
            if featured_url not in images:
                images.insert(0, featured_url)
            item['images'] = images

        item['author'] = 'BruDirect Brunei'
        item['section'] = 'National'

        yield item
