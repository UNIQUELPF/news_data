import scrapy
import re
from news_scraper.spiders.smart_spider import SmartSpider


class JpMextSpider(SmartSpider):
    name = 'jp_mext'
    country_code = 'JPN'
    country = '日本'
    language = 'ja'
    source_timezone = 'Asia/Tokyo'
    allowed_domains = ['mext.go.jp']
    start_urls = ['https://www.mext.go.jp/b_menu/news/index.html']

    use_curl_cffi = False
    strict_date_required = False
    fallback_content_selector = 'article, div#main, main'
    dateparser_settings = {'DATE_ORDER': 'YMD'}

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.0,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 2,
    }

    async def start(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse, dont_filter=True)

    def parse(self, response):
        # Use response.body to handle various Japanese encodings (Shift_JIS, EUC-JP, etc.)
        encoding = response.encoding or 'utf-8'
        try:
            html_text = response.body.decode(encoding, errors='replace')
        except (UnicodeDecodeError, LookupError):
            html_text = response.body.decode('utf-8', errors='replace')

        has_valid_item_in_window = False

        # Extract links via Scrapy selectors (handles encoding natively)
        all_links = response.css('a[href]')

        for a_sel in all_links:
            href = a_sel.attrib.get('href', '')
            if not href or any(x in href for x in ['javascript:', 'mailto:', '#']):
                continue

            url = response.urljoin(href).split('#')[0]

            # Must be on an allowed domain
            if not any(dom in url for dom in self.allowed_domains):
                continue

            # Skip obvious non-article links (top-level index, language switch, etc.)
            if url.rstrip('/') == response.url.rstrip('/'):
                continue

            title_text = a_sel.css('::text').get(default='').strip()
            if len(title_text) < 5:
                title_text = a_sel.xpath('string()').get(default='').strip()
            if len(title_text) < 5:
                continue

            # Search surrounding context for date hints
            date_str = None
            # Try parent elements up to 3 levels
            for ancestor_sel in [a_sel.xpath('..'), a_sel.xpath('../..'), a_sel.xpath('../../..')]:
                ancestor_text = ancestor_sel.xpath('string()').get(default='')
                # Normalize full-width digits to half-width
                ancestor_text = ancestor_text.translate(
                    str.maketrans('０１２３４５６７８９', '0123456789')
                )
                match = re.search(
                    r'(202\d[年/.-]\d{1,2}[月/.-]\d{1,2}日?)',
                    ancestor_text
                )
                if match:
                    date_str = match.group(1)
                    break

            publish_time = self.parse_date(date_str) if date_str else None

            if not self.should_process(url, publish_time):
                continue

            has_valid_item_in_window = True
            meta = {'title_hint': title_text}
            if publish_time:
                meta['publish_time_hint'] = publish_time

            yield scrapy.Request(url, callback=self.parse_detail, meta=meta)

    def parse_detail(self, response):
        item = self.auto_parse_item(response)

        if not self.should_process(response.url, item.get('publish_time')):
            return

        item['author'] = 'Ministry of Education'
        item['section'] = 'Press Release'

        if item.get('content_plain') and len(item['content_plain']) > 100:
            yield item
