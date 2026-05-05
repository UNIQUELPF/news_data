import scrapy
from news_scraper.spiders.smart_spider import SmartSpider


class MyanmarElevenSpider(SmartSpider):
    name = 'mm_eleven'
    country_code = 'MMR'
    country = '缅甸'
    language = 'en'
    source_timezone = 'Asia/Yangon'
    allowed_domains = ['news-eleven.com']
    start_urls = ['https://news-eleven.com/business']
    fallback_content_selector = '.field-name-body'
    strict_date_required = False
    MAX_PAGES = 100

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.0,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 4,
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        }
    }

    def start_requests(self):
        yield scrapy.Request(
            f"{self.start_urls[0]}?page=0",
            callback=self.parse_list,
            meta={'page': 0}
        )

    def parse_list(self, response):
        articles = response.css('.frontpage-title a::attr(href)').getall()
        if not articles:
            articles = response.css('.news-top-featured-large-category a::attr(href)').getall()

        has_valid_item_in_window = False

        for link in articles:
            full_url = response.urljoin(link)
            if '/article/' not in full_url:
                continue
            if self.should_process(full_url):
                has_valid_item_in_window = True
                yield scrapy.Request(full_url, callback=self.parse_article)

        current_page = response.meta.get('page', 0)
        if has_valid_item_in_window and current_page < self.MAX_PAGES:
            next_page = current_page + 1
            next_url = f"{self.start_urls[0]}?page={next_page}"
            yield scrapy.Request(
                next_url,
                callback=self.parse_list,
                meta={'page': next_page},
                dont_filter=True
            )

    def parse_article(self, response):
        item = self.auto_parse_item(
            response,
            title_xpath="//h1[@class='article-title']/text()",
            publish_time_xpath="//meta[@property='article:published_time']/@content",
        )
        item['author'] = 'Eleven Media Group'
        item['section'] = 'Business'
        # 动态语言检测：如标题包含缅甸文则设为 'my'
        title = item.get('title', '')
        if title and any('က' <= char <= '႟' for char in title):
            item['language'] = 'my'

        if item.get('content_plain') and len(item['content_plain']) > 100:
            yield item
