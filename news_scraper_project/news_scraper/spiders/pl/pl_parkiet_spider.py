import scrapy
from datetime import datetime
from news_scraper.spiders.smart_spider import SmartSpider


class PlParkietSpider(SmartSpider):
    name = "pl_parkiet"
    country_code = 'POL'
    country = '波兰'
    language = 'pl'
    source_timezone = 'Europe/Warsaw'
    allowed_domains = ["www.parkiet.com"]
    start_urls = ["https://www.parkiet.com/wiadomosci"]
    fallback_content_selector = '.articleBody.body'

    use_curl_cffi = True
    strict_date_required = False

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "news_scraper.middlewares.CurlCffiMiddleware": 543,
            "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
        },
        "CURLL_CFFI_IMPERSONATE": "chrome120",
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.5,
        "DOWNLOAD_HANDLERS": {
            "http": "scrapy.core.downloader.handlers.http11.HTTP11DownloadHandler",
            "https": "scrapy.core.downloader.handlers.http11.HTTP11DownloadHandler",
        },
    }

    async def start(self):
        yield scrapy.Request(
            self.start_urls[0],
            callback=self.parse,
            dont_filter=True,
        )

    def parse(self, response):
        links = response.css('a.contentLink::attr(href)').getall()
        if not links:
            links = response.css(
                'a[href*="/art"]::attr(href), '
                'a[href*="/gospodarka"]::attr(href), '
                'a[href*="/firmy"]::attr(href), '
                'a[href*="/wiadomosci"]::attr(href)'
            ).getall()
        unique_links = list(set(links))

        has_valid_item_in_window = False

        for link in unique_links:
            if not link.startswith('http'):
                link = "https://www.parkiet.com" + link

            if self.should_process(link):
                has_valid_item_in_window = True
                yield scrapy.Request(
                    link,
                    callback=self.parse_article,
                )

    def parse_article(self, response):
        # Custom date extraction (DD.MM.YYYY HH:MM)
        date_str = response.css('span#livePublishedAtContainer::text').get()
        pub_date = None
        if date_str:
            try:
                pub_date = datetime.strptime(date_str.strip(), "%d.%m.%Y %H:%M")
                pub_date = self.parse_to_utc(pub_date)
            except Exception as e:
                self.logger.warning(f"Could not parse Polish date '{date_str}': {e}")

        item = self.auto_parse_item(response)
        item['publish_time'] = pub_date or item.get('publish_time')
        item['author'] = (response.css('.author .name a::text').get() or "Parkiet.com").strip()
        item['section'] = 'Markets'

        if not self.should_process(response.url, item.get('publish_time')):
            return

        if item.get('content_plain') and len(item['content_plain']) > 50:
            yield item
