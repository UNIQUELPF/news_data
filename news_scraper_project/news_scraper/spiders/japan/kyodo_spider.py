import scrapy
from news_scraper.spiders.smart_spider import SmartSpider


class KyodoSpider(SmartSpider):
    name = 'jp_kyodo'

    country_code = 'JPN'
    country = '日本'
    language = 'ja'
    source_timezone = 'Asia/Tokyo'

    allowed_domains = ['kyodo.co.jp']
    start_urls = ['https://www.kyodo.co.jp/news/']

    fallback_content_selector = 'section.post_container'
    strict_date_required = False

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.0,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 4,
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
            'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
        }
    }

    def start_requests(self):
        yield scrapy.Request(
            self.start_urls[0],
            callback=self.parse_list,
            meta={'page': 1},
            dont_filter=True
        )

    def parse_list(self, response):
        articles = response.css('a.main_archive__content--ttl')

        has_valid_item_in_window = False

        for article in articles:
            url = article.css('::attr(href)').get()
            if not url:
                continue
            url = response.urljoin(url)

            # Attempt date extraction from list page for early filtering
            parent = article.xpath('./..')
            date_str = (
                parent.css('time::text').get() or
                parent.css('[class*="date"]::text').get() or
                parent.xpath('.//time//text()').get()
            )
            publish_time = self.parse_date(date_str.strip()) if date_str else None

            if not self.should_process(url, publish_time):
                continue

            has_valid_item_in_window = True
            yield scrapy.Request(
                url,
                callback=self.parse_detail,
                meta={
                    'title_hint': article.css('::text').get(),
                    'publish_time_hint': publish_time,
                    'section_hint': url.split('/')[3] if len(url.split('/')) > 3 else 'news',
                },
                dont_filter=True
            )

        if has_valid_item_in_window:
            next_page = response.meta['page'] + 1
            yield scrapy.Request(
                f"{self.start_urls[0]}page/{next_page}/",
                callback=self.parse_list,
                meta={'page': next_page},
                dont_filter=True
            )

    def parse_detail(self, response):
        item = self.auto_parse_item(
            response,
            title_xpath="//section[contains(@class,'post_ttl')]//h1/text() | //h1[contains(@class,'main_ttl')]/text()",
            publish_time_xpath="//time[contains(@class,'post_detail__date')]/text()",
        )

        # Date-based filtering on detail page (fallback when list page dates unavailable)
        pub_time = item.get('publish_time')
        if pub_time and not self.should_process(response.url, pub_time):
            return

        item['author'] = 'Kyodo News Japan'
        item['section'] = response.meta.get('section_hint', 'news')

        if item.get('content_plain') and len(item['content_plain']) > 100:
            yield item
