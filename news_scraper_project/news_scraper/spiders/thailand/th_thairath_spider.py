import scrapy
import json
from datetime import datetime
from scrapy.selector import Selector
from news_scraper.spiders.smart_spider import SmartSpider


class ThThairathSpider(SmartSpider):
    name = "th_thairath"
    source_timezone = 'Asia/Bangkok'
    country_code = 'THA'
    country = '泰国'
    language = 'th'

    allowed_domains = ['thairath.co.th']

    base_url = 'https://www.thairath.co.th/news/politic/all-latest?filter=1&page={}'

    use_curl_cffi = True
    fallback_content_selector = ".entry-content"
    strict_date_required = True

    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'CONCURRENT_REQUESTS': 8,
        'DOWNLOAD_DELAY': 1
    }

    async def start(self):
        yield scrapy.Request(
            self.base_url.format(1),
            callback=self.parse,
            meta={'page': 1}
        )

    def parse(self, response):
        has_valid_item_in_window = False
        current_page = response.meta.get('page', 1)

        # Primary: __NEXT_DATA__ extraction (most reliable)
        next_data_script = response.css('script#__NEXT_DATA__::text').get()
        if next_data_script:
            try:
                data = json.loads(next_data_script)
                props = data.get('props', {})
                page_props = props.get('pageProps', {})
                initial_state = page_props.get('initialState') or props.get('initialState', {})

                items = initial_state.get('common', {}).get('data', {}).get('items', [])
                if items:
                    for item in items:
                        path = item.get('fullPath')
                        if not path:
                            continue
                        url = response.urljoin(path)

                        # Try to extract date from listing item
                        pub_time = None
                        pub_time_str = item.get('publishTime')
                        if pub_time_str:
                            try:
                                dt = datetime.fromisoformat(pub_time_str.replace('Z', '+00:00'))
                                pub_time = self.parse_to_utc(dt)
                            except Exception:
                                pass

                        if not self.should_process(url, pub_time):
                            continue

                        has_valid_item_in_window = True
                        meta = {'page': current_page}
                        if pub_time:
                            meta['publish_time_hint'] = pub_time
                        yield scrapy.Request(url, self.parse_article, meta=meta)
            except Exception as e:
                self.logger.error(f"Error parsing __NEXT_DATA__ in listing: {e}")

        # Fallback: extract links from HTML (no dates available)
        if not next_data_script:
            links = response.css('a[href*="/news/politic/"]::attr(href)').getall()
            for link in set(links):
                if any(char.isdigit() for char in link.split('/')[-1]):
                    yield response.follow(link, self.parse_article)
                    has_valid_item_in_window = True

        # Pagination with circuit breaker
        if has_valid_item_in_window:
            next_page = current_page + 1
            yield scrapy.Request(
                self.base_url.format(next_page),
                callback=self.parse,
                meta={'page': next_page}
            )

    def parse_article(self, response):
        # ---- Primary: __NEXT_DATA__ extraction ----
        next_data_script = response.css('script#__NEXT_DATA__::text').get()
        if next_data_script:
            try:
                data = json.loads(next_data_script)
                props = data.get('props', {})
                page_props = props.get('pageProps', {})
                initial_state = page_props.get('initialState') or props.get('initialState', {})

                content_data = initial_state.get('content', {}).get('data', {}).get('items', {})
                if not content_data:
                    content_data = initial_state.get('common', {}).get('data', {}).get('items', [{}])[0]

                title = content_data.get('title', '').strip()
                pub_time_str = content_data.get('publishTime', '')
                content_html = content_data.get('content', '')

                pub_time = None
                if pub_time_str:
                    try:
                        dt = datetime.fromisoformat(pub_time_str.replace('Z', '+00:00'))
                        pub_time = self.parse_to_utc(dt)
                    except Exception:
                        pass

                if not self.should_process(response.url, pub_time):
                    return

                # Clean content from HTML
                sel = Selector(text=content_html)
                content_parts = [p.strip() for p in sel.css('p::text, div::text').getall() if p.strip()]
                content = "\n\n".join(content_parts)

                # Extract image
                images = []
                og_image = response.css('meta[property="og:image"]::attr(content)').get()
                if og_image:
                    images.append(response.urljoin(og_image))

                item = {
                    'url': response.url,
                    'title': title,
                    'content_plain': content,
                    'raw_html': response.text,
                    'publish_time': pub_time,
                    'language': self.language,
                    'section': 'Politic',
                    'country_code': self.country_code,
                    'country': self.country,
                    'author': content_data.get('author') or 'Thairath',
                    'images': images,
                }
                yield item
                return
            except Exception as e:
                self.logger.error(f"Error parsing __NEXT_DATA__ in article {response.url}: {e}")

        # ---- Fallback: standard HTML extraction via auto_parse_item ----
        item = self.auto_parse_item(response)

        if not self.should_process(response.url, item.get('publish_time')):
            return

        item['author'] = 'Thairath'
        item['section'] = 'Politic'
        yield item
