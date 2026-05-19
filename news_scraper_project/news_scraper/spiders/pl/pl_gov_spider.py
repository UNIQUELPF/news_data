import scrapy
import re
from news_scraper.spiders.smart_spider import SmartSpider


class PlGovSpider(SmartSpider):
    name = "pl_gov"
    country_code = 'POL'
    country = '波兰'
    language = 'pl'
    source_timezone = 'Europe/Warsaw'
    allowed_domains = ["www.gov.pl"]
    fallback_content_selector = '.editor-content'
    dateparser_settings = {"DATE_ORDER": "DMY"}

    use_curl_cffi = True
    strict_date_required = False

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "news_scraper.middlewares.CurlCffiMiddleware": 543,
            "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
        },
        "CURLL_CFFI_IMPERSONATE": "chrome120",
        "CONCURRENT_REQUESTS": 1,  # Serial: listing has no dates, detail check one-by-one
        "DOWNLOAD_DELAY": 1.2,
        "PLAYWRIGHT_LAUNCH_OPTIONS": {"headless": True}
    }

    MAX_PAGES = 50

    async def start(self):
        yield scrapy.Request(
            "https://www.gov.pl/web/premier/wydarzenia?page=1",
            callback=self.parse,
            dont_filter=True,
        )

    def parse(self, response):
        links = response.css('div.art-prev ul li .title a::attr(href)').getall()
        if not links:
            links = response.css('a[href*="/web/premier/"]::attr(href)').getall()

        valid_links = []
        for link in links:
            if not link.startswith('http'):
                link = "https://www.gov.pl" + link

            if '/web/premier/wydarzenia' in link or '/web/' not in link or '?page' in link:
                continue

            if self.should_process(link):
                valid_links.append(link)

        # De-duplicate while preserving order
        seen = set()
        unique_links = []
        for l in valid_links:
            if l not in seen:
                seen.add(l)
                unique_links.append(l)

        current_page = 1
        if 'page=' in response.url:
            try:
                current_page = int(response.url.split('page=')[-1].split('&')[0])
            except ValueError:
                pass

        if not unique_links:
            self.logger.info(f"[{self.name}] No valid links to process on page {current_page}. Stopping.")
            return

        state = {
            'pending_count': len(unique_links),
            'dates': [],
            'page': current_page,
            'response_url': response.url
        }

        for url in unique_links:
            yield scrapy.Request(
                url,
                callback=self.parse_article,
                errback=self._handle_detail_error,
                meta={"playwright": True, 'shared_state': state}
            )

    def _check_next_page(self, state, response_url):
        page = state['page']
        parsed_dates = [d for d in state['dates'] if d is not None]

        if parsed_dates and all(d < self.cutoff_date for d in parsed_dates):
            self.logger.info(f"[{self.name}] All articles on page {page} are older than cutoff {self.cutoff_date}. Stopping pagination.")
            return

        if page < self.MAX_PAGES:
            next_page_url = f"https://www.gov.pl/web/premier/wydarzenia?page={page + 1}"
            self.logger.info(f"Proceeding to page {page + 1}: {next_page_url}")
            yield scrapy.Request(
                next_page_url,
                callback=self.parse
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
        # Custom date extraction (DD.MM.YYYY)
        date_str = response.css('p.event-date::text, .date::text, .article-header .date::text').get()
        if not date_str:
            raw_text = response.text
            match = re.search(r'(\d{2}\.\d{2}\.\d{4})', raw_text)
            if match:
                date_str = match.group(1)

        pub_date = None
        if date_str:
            pub_date = self.parse_date(date_str.strip())

        item = self.auto_parse_item(response)
        if item:
            item['publish_time'] = pub_date or item.get('publish_time')
            item['author'] = 'Kancelaria Prezesa Rady Ministrów (KPRM)'
            item['section'] = 'Government Announcements'

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
