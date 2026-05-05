import scrapy
import re
from datetime import datetime
from news_scraper.spiders.smart_spider import SmartSpider


class VnVnexpressSpider(SmartSpider):
    name = "vn_vnexpress"
    source_timezone = 'Asia/Ho_Chi_Minh'

    country_code = 'VNM'
    country = '越南'
    language = 'vi'
    allowed_domains = ["vnexpress.net"]

    strict_date_required = True
    use_curl_cffi = True
    fallback_content_selector = "article.fck_detail"

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "news_scraper.middlewares.CurlCffiMiddleware": 543,
            "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
        },
        "CURLL_CFFI_IMPERSONATE": "chrome120",
        "CONCURRENT_REQUESTS": 8,
        "DOWNLOAD_DELAY": 0.5
    }

    async def start(self):
        """Start with the first listing page."""
        yield scrapy.Request(
            "https://vnexpress.net/kinh-doanh",
            callback=self.parse,
            dont_filter=True
        )

    def parse(self, response):
        """Parse listing page with articles."""
        articles = response.css('article.item-news')
        if not articles:
            articles = response.css('div.item-news')

        has_valid_item_in_window = False

        for article in articles:
            link_node = article.css('h2.title-news a, h3.title-news a')
            link = link_node.attrib.get('href')
            if not link:
                continue

            # Check timestamps from data-publishtime for quick filter
            publish_time = None
            pub_timestamp = article.attrib.get('data-publishtime')
            if pub_timestamp:
                try:
                    dt = datetime.fromtimestamp(int(pub_timestamp))
                    publish_time = self.parse_to_utc(dt)
                except Exception:
                    pass

            if not self.should_process(link, publish_time):
                continue

            has_valid_item_in_window = True
            yield scrapy.Request(
                link,
                callback=self.parse_detail,
                meta={"publish_time_hint": publish_time}
            )

        # Pagination with breaker
        if has_valid_item_in_window:
            current_page = 1
            page_match = re.search(r'-p(\d+)$', response.url.split('?')[0])
            if page_match:
                current_page = int(page_match.group(1))

            next_page = current_page + 1
            next_url = f"https://vnexpress.net/kinh-doanh-p{next_page}"
            yield scrapy.Request(next_url, callback=self.parse)

    def parse_detail(self, response):
        """Parse article detail page with complex date extraction."""
        item = self.auto_parse_item(
            response,
            title_xpath="//h1[contains(@class, 'title-detail')]/text()"
        )

        # Complex date extraction fallback preserving original logic
        if not item.get('publish_time'):
            # Try meta[name="pubdate"]
            date_str = response.css('meta[name="pubdate"]::attr(content)').get()
            if date_str:
                try:
                    # ISO format: 2026-03-31T16:05:09+07:00
                    pub_date = datetime.fromisoformat(date_str.split('+')[0])
                    item['publish_time'] = self.parse_to_utc(pub_date)
                except Exception:
                    pass

            if not item.get('publish_time'):
                # Fallback span.date text
                # Example: Thứ ba, 31/3/2026, 16:05 (GMT+7)
                date_text = response.css('span.date::text').get()
                if date_text:
                    match = re.search(r'(\d{1,2}/\d{1,2}/\d{4})', date_text)
                    if match:
                        try:
                            pub_date = datetime.strptime(match.group(1), "%d/%m/%Y")
                            item['publish_time'] = self.parse_to_utc(pub_date)
                        except Exception:
                            pass

        item['author'] = "VnExpress"
        item['section'] = "Kinh doanh"

        yield item
