import scrapy
from datetime import datetime
from news_scraper.spiders.smart_spider import SmartSpider


class PortugalJornalNegociosSpider(SmartSpider):
    name = 'pt_jornaldenegocios'
    country_code = 'PRT'
    country = '葡萄牙'
    language = 'pt'
    source_timezone = 'Europe/Lisbon'
    start_date = '2024-01-01'
    allowed_domains = ['jornaldenegocios.pt']
    fallback_content_selector = '.texto_noticia'

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.0,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 1,  # Serial: one-by-one detail check
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        }
    }

    async def start(self):
        base_url = 'https://www.jornaldenegocios.pt/economia'
        yield scrapy.Request(base_url, callback=self.parse_list, meta={'index': 0}, dont_filter=True)

    def parse_list(self, response):
        if self._stop_pagination:
            return

        articles = response.xpath('//a[contains(@href, "/detalhe/")]/@href').getall()
        has_valid_item_in_window = False

        for link in articles:
            full_url = response.urljoin(link)
            if self.should_process(full_url):
                has_valid_item_in_window = True
                yield scrapy.Request(full_url, callback=self.parse_article)

        # Dynamic AJAX pagination
        if has_valid_item_in_window:
            current_index = response.meta.get('index', 0)
            next_index = current_index + 12
            next_url = f"https://www.jornaldenegocios.pt/economia/loadmore?friendlyUrl=economia&contentStartIndex={next_index}"
            yield scrapy.Request(
                next_url, callback=self.parse_list,
                meta={'index': next_index}, dont_filter=True
            )

    def parse_article(self, response):
        item = self.auto_parse_item(
            response,
            title_xpath="//h1/text()",
            publish_time_xpath="//meta[@property='article:published_time']/@content",
        )
        if not self.should_process(response.url, item.get('publish_time')):
            self._stop_pagination = True
            return
        item['author'] = 'Jornal de Negócios'
        item['section'] = 'Economia/Empresas'
        if item.get('content_plain') and len(item['content_plain']) > 50:
            yield item
