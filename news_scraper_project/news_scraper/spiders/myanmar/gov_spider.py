import scrapy
import re
from datetime import datetime
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
    dateparser_settings = {"DATE_ORDER": "DMY"}

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.5,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 2,
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        }
    }

    async def start(self):
        base_param = "?_com_liferay_asset_publisher_web_portlet_AssetPublisherPortlet_INSTANCE_idasset354_cur="
        url = f"{self.start_urls[0]}{base_param}1"
        yield scrapy.Request(
            url,
            callback=self.parse_list,
            meta={'page': 1},
        dont_filter=True,
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
        )
        
        # Parse date from content_plain
        content = item.get('content_plain', '')
        pub_date = None
        if content:
            match = re.search(
                r'\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+(\d{1,2}),\s+(\d{4})\b',
                content,
                re.IGNORECASE
            )
            if match:
                month_str = match.group(1).title()
                day = int(match.group(2))
                year = int(match.group(3))
                months = {
                    "January": 1, "Jan": 1, "February": 2, "Feb": 2, "March": 3, "Mar": 3,
                    "April": 4, "Apr": 4, "May": 5, "June": 6, "Jun": 6, "July": 7, "Jul": 7,
                    "August": 8, "Aug": 8, "September": 9, "Sep": 9, "October": 10, "Oct": 10,
                    "November": 11, "Nov": 11, "December": 12, "Dec": 12
                }
                month = months.get(month_str)
                if month:
                    pub_date = datetime(year, month, day)
                    pub_date = self.parse_to_utc(pub_date)

        item['publish_time'] = pub_date or item.get('publish_time')
        item['author'] = 'Myanmar Government Portal'
        item['section'] = 'Latest News'
        item['language'] = 'my'

        if item.get('content_plain') and len(item['content_plain']) > 200:
            yield item
