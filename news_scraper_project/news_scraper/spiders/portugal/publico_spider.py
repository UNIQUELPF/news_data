import scrapy
from datetime import datetime
from news_scraper.spiders.smart_spider import SmartSpider


class PortugalPublicoSpider(SmartSpider):
    name = 'pt_publico'
    country_code = 'PRT'
    country = '葡萄牙'
    language = 'pt'
    source_timezone = 'Europe/Lisbon'
    start_date = '2024-01-01'
    allowed_domains = ['publico.pt']
    fallback_content_selector = '.story__body'
    start_urls = ['https://www.publico.pt/economia']

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.2,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 4,
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        }
    }

    def start_requests(self):
        # Público 翻页格式为 ?page=N
        for page in range(1, 201):
            url = f"{self.start_urls[0]}?page={page}"
            yield scrapy.Request(url, callback=self.parse_list, meta={'page': page})

    def parse_list(self, response):
        # 获取经济版块列表中的文章链接
        articles = response.css('h2.headline a::attr(href)').getall() or \
                   response.css('h4.headline a::attr(href)').getall() or \
                   response.xpath('//a[contains(@href, "/noticia/")]/@href').getall()

        for link in articles:
            base_link = link.split('?')[0]
            full_url = response.urljoin(base_link)

            # 过滤掉非经济类
            if '/202' in full_url:
                yield scrapy.Request(full_url, callback=self.parse_article)

    def parse_article(self, response):
        item = self.auto_parse_item(
            response,
            title_xpath="//h1/text()",
            publish_time_xpath="//meta[@property='article:published_time']/@content",
        )
        item['author'] = response.css('.story__author::text').get() or 'Público Portugal'
        item['section'] = 'Economia'
        if item.get('content_plain') and len(item['content_plain']) > 50:
            if self.should_process(response.url, item.get('publish_time')):
                yield item
