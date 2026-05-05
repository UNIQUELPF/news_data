import scrapy
from news_scraper.spiders.smart_spider import SmartSpider

class CashCHSpider(SmartSpider):
    name = 'ch_cash'
    source_timezone = 'Europe/Zurich'

    country_code = 'CHE'
    country = '瑞士'
    language = 'de'
    allowed_domains = ['cash.ch']

    use_curl_cffi = True
    strict_date_required = True
    fallback_content_selector = "main"

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 2.0,
        'CONCURRENT_REQUESTS': 1,
    }

    async def start(self):
        yield scrapy.Request('https://www.cash.ch/news/top-news', callback=self.parse)

    def parse(self, response):
        # Extract article blocks from listing page
        articles = response.css('article, div[class*="teaser"], div.c_jLL_d9')
        if not articles:
            self.logger.warning(f"No article containers found on {response.url}")
            return

        has_valid_item_in_window = False

        for art in articles:
            link = art.css('a::attr(href)').get()
            if not link or '/news/' not in link:
                continue

            # Date extraction from listing page element
            publish_time_str = art.css('time::attr(datetime), time::text, [class*="date"]::text').get()
            publish_time = self.parse_date(publish_time_str.strip()) if publish_time_str else None

            if not self.should_process(response.urljoin(link), publish_time):
                continue

            has_valid_item_in_window = True
            yield response.follow(
                link,
                self.parse_article,
                meta={'publish_time_hint': publish_time}
            )

        # Pagination: has_valid_item_in_window breaker
        if has_valid_item_in_window:
            next_page = response.css('a.page-loader-next-btn::attr(href)').get()
            if next_page:
                yield response.follow(next_page, self.parse)

    def parse_article(self, response):
        item = self.auto_parse_item(
            response,
            title_xpath="//h1/text() | //span[contains(@class, 'article-title')]/text()",
            publish_time_xpath="//meta[@property='article:published_time']/@content"
        )

        author = response.css('span.author::text').get()
        item['author'] = author.strip() if author else 'cash.ch'
        item['section'] = 'Top News'

        yield item
