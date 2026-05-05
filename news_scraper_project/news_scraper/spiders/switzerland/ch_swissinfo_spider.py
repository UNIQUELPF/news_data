import scrapy
from news_scraper.spiders.smart_spider import SmartSpider

class SwissinfoSpider(SmartSpider):
    name = 'ch_swissinfo'
    source_timezone = 'Europe/Zurich'

    country_code = 'CHE'
    country = '瑞士'
    language = 'en'
    allowed_domains = ['swissinfo.ch', 'www.swissinfo.ch']

    use_curl_cffi = False
    strict_date_required = True
    fallback_content_selector = ".article-main"

    def _playwright_meta(self):
        return {
            'playwright': True,
            'playwright_include_body': True,
            'playwright_page_init_callback': lambda page, request: page.route(
                "**/*",
                lambda route: route.abort()
                if route.request.resource_type in ["image", "media", "font", "stylesheet"]
                else route.continue_()
            ),
            'playwright_page_goto_params': {"wait_until": "domcontentloaded", "timeout": 60000}
        }

    async def start(self):
        yield scrapy.Request(
            'https://www.swissinfo.ch/eng/latest-news/',
            callback=self.parse,
            meta=self._playwright_meta()
        )

    def parse(self, response):
        self.logger.info(f"Analyzing Swissinfo list: {response.url}")

        articles = response.css('article.teaser-wide-card')
        if not articles:
            articles = response.css('article')

        self.logger.info(f"Found {len(articles)} potential articles in list.")

        has_valid_item_in_window = False

        for art in articles:
            link = art.css('a.teaser-wide-card__link::attr(href)').get() or art.css('h3 a::attr(href)').get()
            if not link:
                continue

            # Date extraction from listing page
            publish_time = None
            list_date_str = art.css('time::attr(datetime)').get()
            if list_date_str:
                publish_time = self.parse_date(list_date_str)

            full_url = response.urljoin(link)

            if not self.should_process(full_url, publish_time):
                continue

            has_valid_item_in_window = True
            yield scrapy.Request(
                full_url,
                callback=self.parse_article,
                meta={
                    **self._playwright_meta(),
                    'publish_time_hint': publish_time,
                },
                dont_filter=True
            )

        # Pagination: has_valid_item_in_window breaker
        if has_valid_item_in_window:
            current_offset = getattr(self, 'offset', 0) + 10
            self.offset = current_offset
            if current_offset <= 1000:
                next_url = f"https://www.swissinfo.ch/eng/latest-news/?offset={current_offset}"
                yield scrapy.Request(
                    next_url,
                    callback=self.parse,
                    meta=self._playwright_meta()
                )

    def parse_article(self, response):
        item = self.auto_parse_item(
            response,
            title_xpath="//h1/text()",
            publish_time_xpath="//time/@datetime"
        )

        author = response.css('.author::text').get()
        item['author'] = author.strip() if author else 'swissinfo.ch'
        item['section'] = 'Latest News'

        if item.get('title') or (item.get('content_plain') and len(item.get('content_plain', '')) > 5):
            yield item
