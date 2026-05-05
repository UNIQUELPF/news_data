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
    start_urls = ['https://tek.sapo.pt/ultimas/']

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.0,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 4,
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        }
    }

    def start_requests(self):
        # SAPO Tek 使用标准 WordPress 分页格式 /page/N/
        for page in range(1, 251):
            url = self.start_urls[0] if page == 1 else f"{self.start_urls[0]}page/{page}/"
            yield scrapy.Request(url, callback=self.parse_list, meta={'page': page})

    def parse_list(self, response):
        # 列表中的链接格式通常为 /noticias/.../artigos/...
        articles = response.xpath('//a[contains(@href, "/artigos/")]/@href').getall()

        for link in articles:
            full_url = response.urljoin(link)
            yield scrapy.Request(full_url, callback=self.parse_article)

    def parse_article(self, response):
        item = self.auto_parse_item(
            response,
            title_xpath="//h1/text()",
            publish_time_xpath="//meta[@property='article:published_time']/@content",
        )
        item['author'] = response.css('.article-author::text').get() or 'SAPO TEK Desk'
        item['section'] = 'Tech/Digital'
        if item.get('content_plain') and len(item['content_plain']) > 50:
            if self.should_process(response.url, item.get('publish_time')):
                yield item
