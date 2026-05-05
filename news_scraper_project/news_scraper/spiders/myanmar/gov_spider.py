import scrapy
from news_scraper.spiders.smart_spider import SmartSpider


class MyanmarGovSpider(SmartSpider):
    name = 'mm_gov'
    country_code = 'MMR'
    country = '缅甸'
    language = 'my'
    source_timezone = 'Asia/Yangon'
    allowed_domains = ['myanmar.gov.mm']
    start_urls = ['https://www.myanmar.gov.mm/news-media/news/latest-news']
    fallback_content_selector = '.asset-full-content'
    strict_date_required = False
    MAX_PAGES = 40

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.5,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 2,
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        }
    }

    def start_requests(self):
        base_param = "?_com_liferay_asset_publisher_web_portlet_AssetPublisherPortlet_INSTANCE_idasset354_cur="
        url = f"{self.start_urls[0]}{base_param}1"
        yield scrapy.Request(
            url,
            callback=self.parse_list,
            meta={'page': 1}
        )

    def parse_list(self, response):
        articles = response.css('.asset-title a::attr(href)').getall()
        if not articles:
            articles = response.css('.smallcardstyle a::attr(href)').getall()

        has_valid_item_in_window = False

        for link in articles:
            if not link or '/content/' not in link:
                continue
            if self.should_process(link):
                has_valid_item_in_window = True
                yield scrapy.Request(link, callback=self.parse_article)

        current_page = response.meta.get('page', 1)
        if has_valid_item_in_window and current_page < self.MAX_PAGES:
            next_page = current_page + 1
            base_param = "?_com_liferay_asset_publisher_web_portlet_AssetPublisherPortlet_INSTANCE_idasset354_cur="
            next_url = f"{self.start_urls[0]}{base_param}{next_page}"
            yield scrapy.Request(
                next_url,
                callback=self.parse_list,
                meta={'page': next_page},
                dont_filter=True
            )

    def parse_article(self, response):
        item = self.auto_parse_item(
            response,
            title_xpath="//h1[@class='fontsize24']/text() | //div[@class='asset-content']/h2/text()",
            publish_time_xpath="//meta[@property='article:published_time']/@content",
        )
        item['author'] = 'Myanmar Government Portal'
        item['section'] = 'Latest News'
        item['language'] = 'my'

        if item.get('content_plain') and len(item['content_plain']) > 200:
            yield item
