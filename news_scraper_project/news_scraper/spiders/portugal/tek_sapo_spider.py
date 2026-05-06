import scrapy
from datetime import datetime
from news_scraper.spiders.smart_spider import SmartSpider


class PortugalTekSapoSpider(SmartSpider):
    name = 'pt_tek_sapo'
    country_code = 'PRT'
    country = '葡萄牙'
    language = 'pt'
    source_timezone = 'Europe/Lisbon'
    start_date = '2024-01-01'
    allowed_domains = ['tek.sapo.pt']
    fallback_content_selector = '.article-content'

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.0,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 1,  # Serial: one-by-one detail check
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        }
    }

    async def start(self):
        base_url = 'https://tek.sapo.pt/ultimas/'
        yield scrapy.Request(base_url, callback=self.parse_list, meta={'page': 1}, dont_filter=True)

    def parse_list(self, response):
        if self._stop_pagination:
            return

        articles = response.xpath('//a[contains(@href, "/artigos/")]/@href').getall()
        has_valid_item_in_window = False

        for link in articles:
            full_url = response.urljoin(link)
            if self.should_process(full_url):
                has_valid_item_in_window = True
                yield scrapy.Request(full_url, callback=self.parse_article)

        if has_valid_item_in_window:
            page = response.meta.get('page', 1)
            next_url = f"https://tek.sapo.pt/ultimas/page/{page + 1}/"
            yield scrapy.Request(next_url, callback=self.parse_list, meta={'page': page + 1}, dont_filter=True)

    def parse_article(self, response):
        item = self.auto_parse_item(
            response,
            title_xpath="//h1/text()",
            publish_time_xpath="//meta[@property='article:published_time']/@content",
        )
        if not self.should_process(response.url, item.get('publish_time')):
            self._stop_pagination = True
            return
        item['author'] = response.css('.article-author::text').get() or 'SAPO TEK Desk'
        item['section'] = 'Tech/Digital'
        if item.get('content_plain') and len(item['content_plain']) > 50:
            yield item
