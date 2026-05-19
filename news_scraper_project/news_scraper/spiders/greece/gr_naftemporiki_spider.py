import scrapy
from news_scraper.spiders.smart_spider import SmartSpider


class GrNaftemporikiSpider(SmartSpider):
    name = 'gr_naftemporiki'

    country_code = 'GRC'
    country = '希腊'
    language = 'el'
    source_timezone = 'Europe/Athens'
    use_curl_cffi = True
    dateparser_settings = {"DATE_ORDER": "DMY"}

    # 列表页只有时间 (如 "14:04")，没有完整日期，所以在详情页做日期过滤
    strict_date_required = False
    MAX_PAGES = 50

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
        articles = response.css('div.box-item')

        valid_links = []
        for article in articles:
            url = article.css('div.title a::attr(href)').get()
            if not url:
                continue
            url = response.urljoin(url)

            title_hint = article.css('div.title a::text').get()

            if not self.should_process(url):
                continue

            valid_links.append((url, title_hint))

        current_page = response.meta['page']
        if not valid_links:
            self.logger.info(f"[{self.name}] No valid links on page {current_page}. Stopping.")
            return

        state = {
            'pending_count': len(valid_links),
            'dates': [],
            'page': current_page
        }

        for url, title_hint in valid_links:
            yield scrapy.Request(
                url,
                callback=self.parse_detail,
                errback=self._handle_detail_error,
                meta={
                    'title_hint': title_hint,
                    'section_hint': 'News',
                    'shared_state': state,
                }
            )

    def _check_next_page(self, state):
        page = state['page']
        parsed_dates = [d for d in state['dates'] if d is not None]

        if parsed_dates and all(d < self.cutoff_date for d in parsed_dates):
            self.logger.info(f"[{self.name}] All articles on page {page} are older than cutoff {self.cutoff_date}. Stopping pagination.")
            return

        if page < self.MAX_PAGES:
            next_page = page + 1
            self.logger.info(f"[{self.name}] Proceeding to page {next_page}")
            yield scrapy.Request(
                self.base_url.format(next_page),
                callback=self.parse_list,
                meta={'page': next_page},
                dont_filter=True
            )

    def _handle_detail_error(self, failure):
        self.logger.error(f"Detail request failed: {failure.value}")
        state = failure.request.meta.get('shared_state')
        if state:
            state['pending_count'] -= 1
            if state['pending_count'] == 0:
                for req in self._check_next_page(state):
                    yield req

    def parse_detail(self, response):
        item = self.auto_parse_item(
            response,
            title_xpath="//h1//text()",
            publish_time_xpath="//meta[@property='article:published_time']/@content",
        )

        state = response.meta.get('shared_state')
        pub_time = item.get('publish_time')

        if state:
            state['dates'].append(pub_time)

        if self.should_process(response.url, pub_time):
            item['author'] = 'Naftemporiki Newsroom'
            item['section'] = response.meta.get('section_hint', 'News')
            yield item

        if state:
            state['pending_count'] -= 1
            if state['pending_count'] == 0:
                for req in self._check_next_page(state):
                    yield req
