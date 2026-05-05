import scrapy
from datetime import datetime
from news_scraper.spiders.smart_spider import SmartSpider


class PortugalDNSpider(SmartSpider):
    name = 'pt_dn'
    country_code = 'PRT'
    country = '葡萄牙'
    language = 'pt'
    source_timezone = 'Europe/Lisbon'
    start_date = '2024-01-01'
    allowed_domains = ['dn.pt', 'dinheirovivo.pt']
    fallback_content_selector = '.article-body'

    start_urls = ['https://www.dn.pt/economia/']

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.0,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 4,
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        }
    }

    def start_requests(self):
        yield scrapy.Request(
            self.start_urls[0],
            callback=self.parse_list,
            meta={'page': 1},
            dont_filter=True,
        )

    def parse_list(self, response):
        articles = response.css('h2.headline a::attr(href)').getall() or \
                   response.css('.article-item h2 a::attr(href)').getall() or \
                   response.xpath('//a[contains(@href, "/economia/")]/@href').getall()

        has_valid_item_in_window = False

        for link in articles:
            base_link = link.split('?')[0]
            full_url = response.urljoin(base_link)

            if '/economia/' not in full_url:
                continue

            # Extract publish time hint if available
            pub_time = None
            time_el = response.xpath(f'//a[@href="{link}"]/ancestor::article//time/@datetime').get()
            if time_el:
                pub_time = self.parse_date(time_el)

            if not self.should_process(full_url, pub_time):
                continue

            has_valid_item_in_window = True

            yield scrapy.Request(
                full_url,
                callback=self.parse_article,
                meta={'publish_time_hint': pub_time},
                dont_filter=self.full_scan,
            )

        # Circuit breaker pagination
        if has_valid_item_in_window:
            page = response.meta.get('page', 1) + 1
            url = f"{self.start_urls[0]}page/{page}/"
            yield scrapy.Request(
                url,
                callback=self.parse_list,
                meta={'page': page},
                dont_filter=True,
            )

    def parse_article(self, response):
        item = self.auto_parse_item(
            response,
            title_xpath="//h1/text()",
            publish_time_xpath="//meta[@property='article:published_time']/@content",
        )
        item['author'] = response.css('.article-author::text').get() or 'Global Media Group'
        item['section'] = 'Economia'
        if item.get('content_plain') and len(item['content_plain']) > 50:
            if self.should_process(response.url, item.get('publish_time')):
                yield item
