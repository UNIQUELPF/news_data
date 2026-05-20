import scrapy
from datetime import datetime
import re
from news_scraper.spiders.smart_spider import SmartSpider


class NzMbieSpider(SmartSpider):
    name = "nz_mbie"
    country_code = 'NZL'
    country = '新西兰'
    language = 'en'
    source_timezone = 'Pacific/Auckland'
    allowed_domains = ["mbie.govt.nz"]
    fallback_content_selector = 'div.content-area'

    use_curl_cffi = True
    strict_date_required = False

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "news_scraper.middlewares.CurlCffiMiddleware": 543,
            "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
        },
        "CURLL_CFFI_IMPERSONATE": "chrome120",
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1
    }

    async def start(self):
        yield scrapy.Request(
            "https://www.mbie.govt.nz/about/news?start=0",
            meta={'start': 0},
        dont_filter=True,
        )

    def parse(self, response):
        items = response.css('div.listing-item')
        start = response.meta.get('start', 0)

        has_valid_item_in_window = False
        for item in items:
            link = item.css('a.listing-link.f4::attr(href)').get()
            if not link:
                continue
            full_url = response.urljoin(link)

            # Extract date from listing
            date_text = item.css('span.listing-date::text').get()
            publish_time = None
            if date_text:
                try:
                    date_str = date_text.strip()
                    dt = datetime.strptime(date_str, '%d %B %Y')
                    publish_time = self.parse_to_utc(dt)
                except Exception:
                    pass

            if not self.should_process(full_url, publish_time):
                continue

            has_valid_item_in_window = True
            
            meta = {}
            if publish_time:
                meta['publish_time_hint'] = publish_time
            yield scrapy.Request(full_url, callback=self.parse_article, meta=meta)

        if has_valid_item_in_window:
            next_start = start + 10
            next_url = f"https://www.mbie.govt.nz/about/news?start={next_start}"
            yield scrapy.Request(
                next_url,
                callback=self.parse,
                meta={'start': next_start},
                dont_filter=True
            )

    def parse_article(self, response):
        # Custom date extraction: "Published: 01 January 2026"
        pub_date = None
        date_text = response.xpath("//p[contains(text(), 'Published:')]/text()").get()
        if date_text:
            date_match = re.search(r'Published:\s*(.*)', date_text, re.IGNORECASE)
            if date_match:
                try:
                    pub_date = datetime.strptime(date_match.group(1).strip(), '%d %B %Y')
                    pub_date = self.parse_to_utc(pub_date)
                except Exception:
                    pass

        item = self.auto_parse_item(response)
        item['publish_time'] = pub_date or item.get('publish_time')
        item['author'] = 'New Zealand MBIE'
        item['section'] = 'News'

        if not self.should_process(response.url, item.get('publish_time')):
            return

        if item.get('content_plain') and len(item['content_plain']) > 50:
            yield item
