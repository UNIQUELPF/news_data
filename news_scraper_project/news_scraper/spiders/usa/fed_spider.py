import json
import scrapy
from datetime import datetime
from bs4 import BeautifulSoup
from news_scraper.spiders.smart_spider import SmartSpider


class USAFedSpider(SmartSpider):
    name = 'usa_fed'
    source_timezone = 'America/New_York'

    country_code = 'USA'
    country = '美国'
    language = 'en'
    start_date = '2026-01-01'
    allowed_domains = ['federalreserve.gov']
    strict_date_required = True
    use_curl_cffi = True
    fallback_content_selector = "#article, div.col-xs-12"

    start_urls = ['https://www.federalreserve.gov/json/ne-press.json']
    base_url = 'https://www.federalreserve.gov/'

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.0,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 2,
    }

    async def start(self):
        yield scrapy.Request(self.start_urls[0], callback=self.parse, dont_filter=True)

    def parse(self, response):
        try:
            data = json.loads(response.text)
            has_valid_item_in_window = False
            for record in data:
                relative_url = record.get('l')
                if not relative_url:
                    continue

                full_url = self.base_url + relative_url.lstrip('/')

                # Parse date from Fed JSON format: "3/20/2026 4:30:00 PM"
                pub_time_str = record.get('d')
                publish_time = None
                if pub_time_str:
                    try:
                        publish_time = datetime.strptime(
                            pub_time_str.split(' ')[0], '%m/%d/%Y'
                        )
                    except (ValueError, AttributeError):
                        pass

                if not self.should_process(full_url, publish_time):
                    continue

                has_valid_item_in_window = True
                yield scrapy.Request(
                    full_url,
                    callback=self.parse_detail,
                    meta={
                        'title_hint': record.get('t'),
                        'publish_time_hint': publish_time,
                        'section_hint': record.get('pt'),
                    },
                )
        except Exception as e:
            self.logger.error(f"Fed Index JSON parse failed: {e}")

    def parse_detail(self, response):
        item = self.auto_parse_item(response)

        # ContentEngine fallback: Fed special structure
        if not item.get('content_plain'):
            body = response.css('#article').get() or response.css('div.col-xs-12').get()
            if body:
                soup = BeautifulSoup(body, 'html.parser')
                for tag in soup(['script', 'style', 'button', 'ul.nav', 'div.related-content']):
                    tag.decompose()
                content_parts = []
                for p in soup.find_all(['p', 'h3', 'h4', 'div']):
                    text = p.get_text().strip()
                    if len(text) > 40:
                        content_parts.append(text)
                if content_parts:
                    item['content_plain'] = '\n\n'.join(content_parts)

        # Use JSON metadata as fallback if auto_parse_item missed anything
        if not item.get('title'):
            item['title'] = response.meta.get('title_hint', 'Unknown')

        item['author'] = 'Federal Reserve Board'
        item['section'] = response.meta.get('section_hint', 'Press Release')

        if item.get('content_plain') and len(item['content_plain']) > 150:
            yield item
