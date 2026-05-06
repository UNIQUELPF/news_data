import scrapy
from datetime import datetime
from news_scraper.spiders.smart_spider import SmartSpider


class PortugalCMSpider(SmartSpider):
    name = 'pt_cm'
    country_code = 'PRT'
    country = '葡萄牙'
    language = 'pt'
    source_timezone = 'Europe/Lisbon'
    start_date = '2024-01-01'
    allowed_domains = ['cmjornal.pt']
    fallback_content_selector = '.texto_noticia'
    start_urls = ['https://www.cmjornal.pt/economia']

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.0,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 4,
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        }
    }

    async def start(self):
        # 初始抓取第一页
        yield scrapy.Request(
            self.start_urls[0],
            callback=self.parse_list,
            meta={'index': 0},
            dont_filter=True,
        )

    def parse_list(self, response):
        if self._stop_pagination:
            return
        # CM 的链接格式通常为 /economia/detalhe/...
        articles = response.xpath('//a[contains(@href, "/detalhe/")]/@href').getall()

        has_valid_item_in_window = False
        for link in articles:
            full_url = response.urljoin(link)
            if self.should_process(full_url):
                has_valid_item_in_window = True
                yield scrapy.Request(full_url, callback=self.parse_article)

        if has_valid_item_in_window:
            current_index = response.meta.get('index', 0)
            next_index = current_index + 12
            if next_index < 3600:
                next_url = f"https://www.cmjornal.pt/economia/loadmore?friendlyUrl=economia&contentStartIndex={next_index}"
                yield scrapy.Request(next_url, callback=self.parse_list, meta={'index': next_index})

    def parse_article(self, response):
        item = self.auto_parse_item(
            response,
            title_xpath="//h1/text()",
            publish_time_xpath="//meta[@property='article:published_time']/@content",
        )
        item['author'] = 'Correio da Manhã'
        item['section'] = 'Economia'
        if not self.should_process(response.url, item.get('publish_time')):
            self._stop_pagination = True
            return

        if item.get('content_plain') and len(item['content_plain']) > 50:
            yield item
