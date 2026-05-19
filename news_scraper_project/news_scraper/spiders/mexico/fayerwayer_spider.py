import scrapy
from news_scraper.spiders.smart_spider import SmartSpider


class MexicoFayerWayerSpider(SmartSpider):
    name = 'mexico_fayerwayer'
    country_code = 'MEX'
    country = '墨西哥'
    language = 'es'
    source_timezone = 'America/Mexico_City'
    allowed_domains = ['fayerwayer.com']
    start_urls = ['https://www.fayerwayer.com/comercial/']
    fallback_content_selector = '.article-body'
    strict_date_required = False
    MAX_PAGES = 80
    dateparser_settings = {"DATE_ORDER": "DMY"}

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.0,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 4,
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        }
    }

    async def start(self):
        yield scrapy.Request(
            self.start_urls[0],
            callback=self.parse_list,
            meta={'page': 1},
            dont_filter=True,
        )

    def parse_list(self, response):
        articles = response.css('.b-results-list a.c-link::attr(href)').getall()
        if not articles:
            articles = response.css('a.c-link::attr(href)').getall()

        valid_links = []
        for link in articles:
            if '/202' not in link:
                continue
            full_url = response.urljoin(link)
            if self.should_process(full_url):
                valid_links.append(full_url)

        current_page = response.meta.get('page', 1)
        if not valid_links:
            self.logger.info(f"[{self.name}] No valid links to process on page {current_page}. Stopping.")
            return

        state = {
            'pending_count': len(valid_links),
            'dates': [],
            'page': current_page
        }

        for url in valid_links:
            yield scrapy.Request(
                url,
                callback=self.parse_article,
                errback=self.handle_detail_error,
                meta={'shared_state': state}
            )

    def _check_next_page(self, state):
        page = state['page']
        parsed_dates = [d for d in state['dates'] if d is not None]

        if parsed_dates and all(d < self.cutoff_date for d in parsed_dates):
            self.logger.info(f"[{self.name}] All articles on page {page} are older than cutoff {self.cutoff_date}. Stopping pagination.")
            return

        if page < self.MAX_PAGES:
            next_page = page + 1
            next_url = f"{self.start_urls[0]}page/{next_page}/"
            self.logger.info(f"[{self.name}] Crawling next page {next_page}: {next_url}")
            yield scrapy.Request(
                next_url,
                callback=self.parse_list,
                meta={'page': next_page},
                dont_filter=True
            )

    def handle_detail_error(self, failure):
        self.logger.error(f"Detail request failed: {failure.value}")
        state = failure.request.meta.get('shared_state')
        if state:
            state['pending_count'] -= 1
            if state['pending_count'] == 0:
                for req in self._check_next_page(state):
                    yield req

    def parse_article(self, response):
        item = self.auto_parse_item(
            response,
            title_xpath="//h1/text()",
            publish_time_xpath="//time[@class='c-date']/@dateTime",
        )
        item['author'] = response.css('.c-attribution a::text').get() or 'FayerWayer Mexico'
        item['section'] = 'Tech & Business'

        state = response.meta.get('shared_state')
        if state:
            state['dates'].append(item.get('publish_time'))

        if self.should_process(response.url, item.get('publish_time')):
            if item.get('content_plain') and len(item['content_plain']) > 200:
                yield item

        if state:
            state['pending_count'] -= 1
            if state['pending_count'] == 0:
                for req in self._check_next_page(state):
                    yield req
