import scrapy
import re
from datetime import datetime
from news_scraper.spiders.smart_spider import SmartSpider


class VnBaochinhphuSpider(SmartSpider):
    name = "vn_baochinhphu"
    source_timezone = 'Asia/Ho_Chi_Minh'

    country_code = 'VNM'
    country = '越南'
    language = 'vi'
    allowed_domains = ["baochinhphu.vn"]

    strict_date_required = True
    use_curl_cffi = True
    fallback_content_selector = "div.detail-content"

    dateparser_settings = {'DATE_ORDER': 'DMY'}

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "news_scraper.middlewares.CurlCffiMiddleware": 543,
            "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
        },
        "CURLL_CFFI_IMPERSONATE": "chrome120",
        "CONCURRENT_REQUESTS": 12,
        "DOWNLOAD_DELAY": 0.3
    }

    async def start(self):
        """Start with the first timeline page."""
        yield scrapy.Request(
            "https://baochinhphu.vn/timelinelist/1027/1.htm",
            callback=self.parse,
            headers={"Referer": "https://baochinhphu.vn/kinh-te.htm"},
            dont_filter=True
        )

    def parse(self, response):
        """Parse timeline AJAX responses."""
        articles = response.css('div.box-category-item, div.box-stream-item')

        has_valid_item_in_window = False

        for article in articles:
            link_node = article.css(
                'a.box-category-link-title, a.box-stream-link-title, a[data-type="title"]'
            )
            link = link_node.attrib.get('href')
            if not link:
                continue
            if not link.startswith('http'):
                link = "https://baochinhphu.vn" + link

            # URL date hint extraction: indices 3-8 of the numeric part (YYMMDD)
            publish_time = None
            match = re.search(r'(\d{18})', link)
            if match:
                id_part = match.group(1)
                date_hint = id_part[3:9]
                try:
                    dt = datetime.strptime(date_hint, "%y%m%d")
                    publish_time = self.parse_to_utc(dt)
                except Exception:
                    pass

            if not self.should_process(link, publish_time):
                continue

            has_valid_item_in_window = True
            yield scrapy.Request(
                link,
                callback=self.parse_detail,
                headers={"Referer": "https://baochinhphu.vn/kinh-te.htm"},
                meta={"publish_time_hint": publish_time}
            )

        # Pagination with breaker
        if has_valid_item_in_window:
            current_page = 1
            page_match = re.search(r'/timelinelist/1027/(\d+)\.htm', response.url)
            if page_match:
                current_page = int(page_match.group(1))

            next_page = current_page + 1
            next_url = f"https://baochinhphu.vn/timelinelist/1027/{next_page}.htm"
            yield scrapy.Request(
                next_url,
                callback=self.parse,
                    headers={"Referer": "https://baochinhphu.vn/kinh-te.htm"}
                )

    def parse_detail(self, response):
        """Parse article detail page."""
        item = self.auto_parse_item(
            response,
            title_xpath="//*[contains(@class, 'detail-title')]/text()",
            publish_time_xpath="//*[contains(@class, 'detail-time')]/text()"
        )

        item['author'] = "Vietnam Government"
        item['section'] = "Kinh tế"

        yield item
