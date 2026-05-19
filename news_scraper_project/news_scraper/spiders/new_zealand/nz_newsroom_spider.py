import scrapy
import json
from datetime import datetime
from news_scraper.spiders.smart_spider import SmartSpider


class NzNewsroomSpider(SmartSpider):
    name = "nz_newsroom"
    country_code = 'NZL'
    country = '新西兰'
    language = 'en'
    source_timezone = 'Pacific/Auckland'
    allowed_domains = ["newsroom.co.nz"]
    fallback_content_selector = '.entry-content'

    use_curl_cffi = True
    strict_date_required = False

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "news_scraper.middlewares.CurlCffiMiddleware": 543,
            "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
        },
        "CURLL_CFFI_IMPERSONATE": "chrome120",
        "CONCURRENT_REQUESTS": 4,
        "DOWNLOAD_DELAY": 1
    }

    MAX_PAGES = 50

    async def start(self):
        yield scrapy.Request(
            "https://newsroom.co.nz/category/economy/",
            callback=self.parse,
            dont_filter=True,
        )

    def parse(self, response):
        article_links = response.css('a[rel="bookmark"]::attr(href)').getall()
        valid_links = []
        for link in article_links:
            full_url = response.urljoin(link)
            if self.should_process(full_url):
                valid_links.append(full_url)

        # De-duplicate while preserving order
        seen = set()
        unique_links = []
        for l in valid_links:
            if l not in seen:
                seen.add(l)
                unique_links.append(l)

        current_page = response.meta.get('page', 1)
        if not unique_links:
            self.logger.info(f"[{self.name}] No valid links to process on page {current_page}. Stopping.")
            return

        next_page = response.css('a.next.page-numbers::attr(href)').get()

        state = {
            'pending_count': len(unique_links),
            'dates': [],
            'page': current_page,
            'response_url': response.url,
            'next_page_url': next_page
        }

        for url in unique_links:
            yield scrapy.Request(
                url,
                callback=self.parse_article,
                errback=self._handle_detail_error,
                meta={'shared_state': state}
            )

    def _check_next_page(self, state, response_url):
        page = state['page']
        parsed_dates = [d for d in state['dates'] if d is not None]

        if parsed_dates and all(d < self.cutoff_date for d in parsed_dates):
            self.logger.info(f"[{self.name}] All articles on page {page} are older than cutoff {self.cutoff_date}. Stopping pagination.")
            return

        next_page = state.get('next_page_url')
        if next_page and page < self.MAX_PAGES:
            self.logger.info(f"[{self.name}] Proceeding to page {page + 1}: {next_page}")
            yield scrapy.Request(
                next_page,
                callback=self.parse,
                meta={'page': page + 1}
            )

    def _handle_detail_error(self, failure):
        self.logger.error(f"Detail request failed: {failure.value}")
        state = failure.request.meta.get('shared_state')
        if state:
            state['pending_count'] -= 1
            if state['pending_count'] == 0:
                for req in self._check_next_page(state, state['response_url']):
                    yield req

    def parse_article(self, response):
        state = response.meta.get('shared_state')
        # Custom date extraction from LD-JSON
        pub_date = None
        ld_jsons = response.css('script[type="application/ld+json"]::text').getall()
        for raw in ld_jsons:
            try:
                data = json.loads(raw)
                graph = data.get('@graph', [data]) if isinstance(data, dict) else [data]
                for item in graph:
                    if isinstance(item, dict) and item.get('@type') in ['NewsArticle', 'Article', 'BlogPosting']:
                        date_str = item.get('datePublished')
                        if date_str:
                            pub_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                            pub_date = self.parse_to_utc(pub_date)
                            break
                if pub_date:
                    break
            except Exception:
                continue

        if not pub_date:
            date_meta = response.css('time.entry-date.published::attr(datetime)').get()
            if date_meta:
                try:
                    pub_date = datetime.fromisoformat(date_meta.replace('Z', '+00:00'))
                    pub_date = self.parse_to_utc(pub_date)
                except Exception:
                    pass

        item = self.auto_parse_item(response)
        if item:
            item['publish_time'] = pub_date or item.get('publish_time')
            item['author'] = response.css('.author-name a::text').get("Newsroom")
            item['section'] = 'Economy'

        pub_time = item.get('publish_time') if item else None

        if state:
            state['dates'].append(pub_time)

        if item and item.get('title') and item.get('content_plain') and self.should_process(response.url, pub_time):
            if item.get('content_plain') and len(item['content_plain']) > 50:
                yield item

        if state:
            state['pending_count'] -= 1
            if state['pending_count'] == 0:
                for req in self._check_next_page(state, response.url):
                    yield req
