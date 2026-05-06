import scrapy
from urllib.parse import urlparse, parse_qs
from news_scraper.spiders.smart_spider import SmartSpider

class FinewsCHSpider(SmartSpider):
    name = 'ch_finews'
    source_timezone = 'Europe/Zurich'

    country_code = 'CHE'
    country = '瑞士'
    language = 'en'
    allowed_domains = ['finews.com']

    use_curl_cffi = True
    strict_date_required = True
    fallback_content_selector = "div.item-fulltext"

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.5,
        'CONCURRENT_REQUESTS': 4,
    }

    async def start(self):
        yield scrapy.Request('https://www.finews.com/news/english-news', callback=self.parse)

    def parse(self, response):
        if self._stop_pagination:
            return

        articles = response.css('div.teaser-element')
        if not articles:
            self.logger.warning(f"No article containers found on {response.url}")
            return

        has_valid_item_in_window = False

        for article in articles:
            link = article.css('a::attr(href)').get()
            if not link:
                continue

            # Date extraction from listing page
            publish_time_str = article.css('time::attr(datetime), span.date::text, [class*="date"]::text').get()
            publish_time = self.parse_date(publish_time_str.strip()) if publish_time_str else None

            if not self.should_process(response.urljoin(link), publish_time):
                continue

            has_valid_item_in_window = True
            yield response.follow(
                link,
                self.parse_article,
                meta={'publish_time_hint': publish_time}
            )

        # Pagination: ?start=19, 38, ...
        if has_valid_item_in_window:
            parsed = urlparse(response.url)
            params = parse_qs(parsed.query)
            current_start = int(params.get('start', [0])[0])

            next_start = current_start + 19
            if next_start <= 200:
                next_url = f"https://www.finews.com/news/english-news?start={next_start}"
                yield response.follow(next_url, self.parse)

    def parse_article(self, response):
        item = self.auto_parse_item(
            response,
            title_xpath="//h2[contains(@class, 'item-title')]/text() | //h1/text()",
            publish_time_xpath="//span[contains(@class, 'article-date')]/@content | //meta[@property='article:published_time']/@content"
        )

        author = response.css('span.author-name::text').get()
        item['author'] = author.strip() if author else 'finews.com'
        item['section'] = 'Financial News'

        if not self.should_process(response.url, item.get('publish_time')):
            self._stop_pagination = True
            return

        yield item
