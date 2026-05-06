import scrapy
from news_scraper.spiders.smart_spider import SmartSpider


class GrNaftemporikiSpider(SmartSpider):
    name = 'gr_naftemporiki'

    country_code = 'GRC'
    country = '希腊'
    language = 'el'
    source_timezone = 'Europe/Athens'
    use_curl_cffi = True

    # 列表页只有时间 (如 "14:04")，没有完整日期，所以在详情页做日期过滤
    strict_date_required = False

    allowed_domains = ['naftemporiki.gr']

    base_url = 'https://www.naftemporiki.gr/newsroom/page/{}/'

    fallback_content_selector = 'article.news-article, main.main'

    custom_settings = {
        'DOWNLOAD_DELAY': 0.5,
        'DOWNLOAD_TIMEOUT': 30,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 2,
    }

    async def start(self):
        yield scrapy.Request(
            self.base_url.format(1),
            callback=self.parse_list,
            meta={'page': 1},
            dont_filter=True
        )

    def parse_list(self, response):
        if self._stop_pagination:
            return

        articles = response.css('div.box-item')

        has_valid_item_in_window = False

        for article in articles:
            url = article.css('div.title a::attr(href)').get()
            if not url:
                continue
            url = response.urljoin(url)

            title_hint = article.css('div.title a::text').get()

            # No date on listing page; check dedup via should_process.
            # Date filtering happens on detail page via _stop_pagination.
            if not self.should_process(url):
                continue

            has_valid_item_in_window = True
            yield scrapy.Request(
                url,
                callback=self.parse_detail,
                meta={
                    'title_hint': title_hint,
                    'section_hint': 'News',
                }
            )

        current_page = response.meta['page']
        if has_valid_item_in_window:
            next_page = current_page + 1
            yield scrapy.Request(
                self.base_url.format(next_page),
                callback=self.parse_list,
                meta={'page': next_page},
                dont_filter=True
            )

    def parse_detail(self, response):
        item = self.auto_parse_item(
            response,
            title_xpath="//h1//text()",
            publish_time_xpath="//meta[@property='article:published_time']/@content",
        )

        # Date filtering on detail page: stop pagination when article is too old
        pub_time = item.get('publish_time')
        if not self.should_process(response.url, pub_time):
            self._stop_pagination = True
            return

        item['author'] = 'Naftemporiki Newsroom'
        item['section'] = response.meta.get('section_hint', 'News')

        yield item
