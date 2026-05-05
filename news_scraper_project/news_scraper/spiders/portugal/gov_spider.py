import scrapy
from datetime import datetime
from dateutil import parser as dateutil_parser
from news_scraper.spiders.smart_spider import SmartSpider


class PortugalGovSpider(SmartSpider):
    name = 'pt_gov'
    country_code = 'PRT'
    country = '葡萄牙'
    language = 'pt'
    source_timezone = 'Europe/Lisbon'
    start_date = '2024-01-01'
    allowed_domains = ['portugal.gov.pt']
    fallback_content_selector = 'div#regText.gov-texts'
    start_urls = ['https://www.portugal.gov.pt/pt/gc25/comunicacao/noticias']

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.5,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 2,
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        }
    }

    def start_requests(self):
        # 葡萄牙政府站翻页通常支持 p 参数
        for page in range(1, 76):
            url = f"{self.start_urls[0]}?p={page}"
            yield scrapy.Request(url, callback=self.parse_list, meta={'page': page})

    def parse_list(self, response):
        self.logger.info(f"Received response from {response.url} with length {len(response.text)}")
        # 更加宽松的链接提取逻辑
        articles = response.xpath('//a[contains(@href, "/noticia?")]/@href').getall()
        self.logger.info(f"Discovered {len(articles)} potential articles on {response.url}")

        for link in articles:
            full_url = response.urljoin(link)
            yield scrapy.Request(full_url, callback=self.parse_article)

    def parse_article(self, response):
        item = self.auto_parse_item(
            response,
            title_xpath="//h1/text()",
        )
        self.logger.info(f"Parsing article: {item.get('title')} at {response.url}")

        # 自定义日期解析：政府站的日期格式为 "dd/mm/yyyy às HHhMM"
        pub_time_raw = response.css('div.time::text').get()
        if pub_time_raw:
            self.logger.info(f"Found date raw: {pub_time_raw}")
            try:
                clean_date = pub_time_raw.replace('às', '').replace('h', ':').strip()
                pub_time = dateutil_parser.parse(clean_date)
                item['publish_time'] = self.parse_to_utc(pub_time)
            except Exception as e:
                self.logger.warning(f"Date parse failed for {pub_time_raw}: {e}")

        item['author'] = 'Governo da República Portuguesa'
        item['section'] = 'Comunicado Oficial'

        if item.get('content_plain') and len(item['content_plain']) > 50:
            if self.should_process(response.url, item.get('publish_time')):
                self.logger.info(f"Scraped article: {item.get('title')} - {response.url}")
                yield item
