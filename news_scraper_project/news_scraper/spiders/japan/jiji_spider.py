import scrapy
from news_scraper.spiders.smart_spider import SmartSpider

class JijiSpider(SmartSpider):
    name = 'jp_jiji'

    country_code = 'JPN'
    country = '日本'
    language = 'ja'
    source_timezone = 'Asia/Tokyo'

    allowed_domains = ['jiji.com']

    fallback_content_selector = '.ArticleText'

    # List pages do not carry per-article publish dates, so we rely on
    # the detail page for date extraction and allow undated URLs through.
    strict_date_required = False

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.0,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 2,
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
            'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
        }
    }

    def start_requests(self):
        # 模式 1: Archive 回溯
        # offset 0: 当月, 1: 前月, 2: 前々月
        archives = [
            'https://www.jiji.com/jc/archives?g=eco_archive_0',
            'https://www.jiji.com/jc/archives?g=eco_archive_1',
            'https://www.jiji.com/jc/archives?g=eco_archive_2'
        ]
        for url in archives:
            for page in range(1, 11):
                page_url = f"{url}&p={page}"
                yield scrapy.Request(page_url, callback=self.parse_list, dont_filter=True)

        # 模式 2: 当前列表 (增量)
        yield scrapy.Request('https://www.jiji.com/jc/list?g=eco', callback=self.parse_list, dont_filter=True)

    def parse_list(self, response):
        links = response.css('a[href*="/jc/article?k="]::attr(href)').getall()

        has_valid_item_in_window = False

        for link in links:
            if 'k=' not in link:
                continue

            full_url = response.urljoin(link)

            if not self.should_process(full_url):
                continue

            has_valid_item_in_window = True

            # No dont_filter here: the same article URL appears on every
            # archive page, so we let Scrapy's RFPDupeFilter deduplicate.
            yield scrapy.Request(
                full_url,
                callback=self.parse_article,
            )

        # Archive pages use fixed pagination (1-10); the current list page
        # has no pagination.  has_valid_item_in_window is tracked to follow
        # the V2 convention and would gate pagination if we ever switch to
        # an unbounded date-descending listing.

    def parse_article(self, response):
        item = self.auto_parse_item(
            response,
            title_xpath="//div[contains(@class,'ArticleTitle')]//h1//text()",
            publish_time_xpath="//meta[@itemprop='datePublished']/@content",
        )

        # If the detail page had no publish time (unlikely but defensive),
        # drop the item — SmartSpider strict_date_required=False on the
        # list phase means we may only catch this here.
        if not item.get('publish_time'):
            return

        item['author'] = 'Jiji Press'
        item['section'] = 'Economy'

        if item.get('content_plain') and len(item['content_plain']) > 50:
            yield item
