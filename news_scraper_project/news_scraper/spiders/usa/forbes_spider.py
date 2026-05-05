import json
import re
import scrapy
from datetime import datetime
from bs4 import BeautifulSoup
from news_scraper.spiders.smart_spider import SmartSpider


class USAForbesSpider(SmartSpider):
    name = 'usa_forbes'
    source_timezone = 'America/New_York'

    country_code = 'USA'
    country = '美国'
    language = 'en'
    start_date = '2026-01-01'
    allowed_domains = ['forbes.com']
    strict_date_required = True
    use_curl_cffi = True
    fallback_content_selector = "div.article-body-container, .article-body"

    start_urls = ['https://www.forbes.com/money/']

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.0,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 8,
    }

    async def start(self):
        yield scrapy.Request(self.start_urls[0], callback=self.parse)

    def parse(self, response):
        """Parse the Forbes listing HTML page, then trigger API pagination."""
        has_valid_item_in_window = False

        # CSS extraction for article links
        for a in response.css('a.kZ_L0i_J::attr(href)'):
            link = a.get()
            if not link or '/202' not in link:
                continue

            full_url = response.urljoin(link)

            # Extract date from URL pattern: /2026/03/15/title/
            publish_time = None
            date_match = re.search(r'/(\d{4})/(\d{2})/(\d{2})/', full_url)
            if date_match:
                try:
                    publish_time = datetime(
                        int(date_match.group(1)),
                        int(date_match.group(2)),
                        int(date_match.group(3)),
                    )
                except ValueError:
                    pass

            if not self.should_process(full_url, publish_time):
                continue

            has_valid_item_in_window = True
            meta = {'section_hint': 'Money'}
            if publish_time:
                meta['publish_time_hint'] = publish_time
            yield scrapy.Request(full_url, callback=self.parse_detail, meta=meta)

        # Trigger API pagination for deeper historical articles
        if has_valid_item_in_window:
            yield from self.request_api(start=0)

    def request_api(self, start):
        """Forbes simple-data API request with offset-based pagination."""
        api_url = f"https://www.forbes.com/simple-data/channel/money/?start={start}&size=50"
        yield scrapy.Request(
            api_url,
            callback=self.parse_api_json,
            meta={'start': start},
            dont_filter=True,
            handle_httpstatus_list=[403],
        )

    def parse_api_json(self, response):
        """Parse Forbes API JSON response with date-aware pagination."""
        if response.status == 403:
            self.logger.info("Forbes simple-data API returned 403, skipping API pagination fallback.")
            return

        try:
            data = json.loads(response.text)
            articles = data if isinstance(data, list) else data.get('articles', [])

            if not articles:
                return

            has_valid_item_in_window = False
            for art in articles:
                uri = art.get('uri') or art.get('url')
                if not uri:
                    continue

                # Parse publish_time from API response
                pub_ts = art.get('date') or art.get('published_date')
                if pub_ts:
                    if isinstance(pub_ts, int):
                        pub_dt = datetime.fromtimestamp(pub_ts / 1000)
                    else:
                        try:
                            pub_dt = datetime.fromisoformat(pub_ts.replace('Z', '+00:00'))
                        except (ValueError, AttributeError):
                            pub_dt = datetime.now()
                else:
                    pub_dt = datetime.now()

                pub_dt = pub_dt.replace(tzinfo=None)

                if not self.should_process(response.urljoin(uri), pub_dt):
                    # Stop pagination when articles predate the cutoff
                    if pub_dt and self.cutoff_date and pub_dt < self.cutoff_date:
                        self.logger.info("Reached cutoff date, stopping Forbes API pagination.")
                        return
                    continue

                has_valid_item_in_window = True
                yield scrapy.Request(
                    response.urljoin(uri),
                    callback=self.parse_detail,
                    meta={'publish_time_hint': pub_dt, 'section_hint': 'Money'},
                )

            # Continue pagination if articles are still within the window
            next_start = response.meta['start'] + 50
            if has_valid_item_in_window:
                yield from self.request_api(next_start)
        except Exception as e:
            self.logger.error(f"Forbes API error: {e}")

    def parse_detail(self, response):
        item = self.auto_parse_item(
            response,
            title_xpath="//h1[contains(@class, 'fs-headline')]/text()",
        )

        # ContentEngine fallback: Forbes specific cleaning
        if not item.get('content_plain'):
            content_html = response.css('div.article-body-container').get() or response.css('.article-body').get()
            if content_html:
                soup = BeautifulSoup(content_html, 'html.parser')
                for tag in soup(['script', 'style', 'aside', 'button', 'ul.related-content']):
                    tag.decompose()
                text = soup.get_text(separator='\n')
                lines = [line.strip() for line in text.splitlines() if line.strip() and len(line.strip()) > 30]
                if lines:
                    item['content_plain'] = '\n\n'.join(lines)

        item['author'] = response.css('a.author-name--desktop::text').get() or 'Forbes'
        item['section'] = response.meta.get('section_hint', 'Money')

        if item.get('content_plain') and len(item['content_plain']) > 100:
            yield item
