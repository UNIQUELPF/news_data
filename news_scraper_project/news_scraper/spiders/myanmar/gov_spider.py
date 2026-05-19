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

        urls_to_process = []
        for link in articles:
            if not link or '/content/' not in link:
                continue
            if self.should_process(link):
                urls_to_process.append(link)

        current_page = response.meta.get('page', 1)

        if urls_to_process:
            next_url = urls_to_process.pop(0)
            yield scrapy.Request(
                next_url,
                callback=self.parse_article_sync,
                meta={
                    'urls_to_process': urls_to_process,
                    'any_item_new': False,
                    'page': current_page
                }
            )
        else:
            self.logger.info(f"No new/valid URLs on page {current_page}. Stopping pagination.")

    def parse_article_sync(self, response):
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

        pub_time = pub_date or item.get('publish_time')
        item['publish_time'] = pub_time
        item['author'] = 'Myanmar Government Portal'
        item['section'] = 'Latest News'
        item['language'] = 'my'

        # Check if the extracted publish date is valid and within the window
        is_new = False
        if pub_time:
            is_new = self.should_process(response.url, pub_time)
        else:
            is_new = not self.strict_date_required

        if is_new:
            response.meta['any_item_new'] = True
            if item.get('content_plain') and len(item['content_plain']) > 200:
                yield item

        # Process the remaining URLs for this list page
        urls_to_process = response.meta.get('urls_to_process', [])
        current_page = response.meta.get('page', 1)
        any_item_new = response.meta.get('any_item_new', False)

        if urls_to_process:
            next_url = urls_to_process.pop(0)
            yield scrapy.Request(
                next_url,
                callback=self.parse_article_sync,
                meta={
                    'urls_to_process': urls_to_process,
                    'any_item_new': any_item_new,
                    'page': current_page
                }
            )
        else:
            # All URLs for this list page are processed! Now decide if we should load the next page
            if any_item_new and current_page < self.MAX_PAGES:
                next_page = current_page + 1
                base_param = "?_com_liferay_asset_publisher_web_portlet_AssetPublisherPortlet_INSTANCE_idasset354_cur="
                next_url = f"{self.start_urls[0]}{base_param}{next_page}"
                self.logger.info(f"Page {current_page} had new articles. Proceeding to page {next_page}: {next_url}")
                yield scrapy.Request(
                    next_url,
                    callback=self.parse_list,
                    meta={'page': next_page},
                    dont_filter=True
                )
            else:
                self.logger.info(f"All articles on page {current_page} were old or already scraped. Stopping pagination.")
