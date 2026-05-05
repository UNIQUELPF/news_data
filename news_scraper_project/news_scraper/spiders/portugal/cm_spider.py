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

    def start_requests(self):
        # 初始抓取第一页
        yield scrapy.Request(self.start_urls[0], callback=self.parse_list)

        # 模拟 AJAX 翻页逻辑：步长 12
        base_ajax = "https://www.cmjornal.pt/economia/loadmore?friendlyUrl=economia&contentStartIndex="
        for index in range(12, 3600, 12):
            url = f"{base_ajax}{index}"
            yield scrapy.Request(url, callback=self.parse_list, meta={'index': index})

    def parse_list(self, response):
        # CM 的链接格式通常为 /economia/detalhe/...
        articles = response.xpath('//a[contains(@href, "/detalhe/")]/@href').getall()

        for link in articles:
            full_url = response.urljoin(link)
            yield scrapy.Request(full_url, callback=self.parse_article)

    def parse_article(self, response):
        item = self.auto_parse_item(
            response,
            title_xpath="//h1/text()",
            publish_time_xpath="//meta[@property='article:published_time']/@content",
        )
        item['author'] = 'Correio da Manhã'
        item['section'] = 'Economia'
        if item.get('content_plain') and len(item['content_plain']) > 50:
            if self.should_process(response.url, item.get('publish_time')):
                yield item
