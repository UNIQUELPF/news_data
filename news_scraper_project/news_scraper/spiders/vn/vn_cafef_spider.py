import scrapy
import re
from datetime import datetime
from news_scraper.spiders.smart_spider import SmartSpider


class VnCafefSpider(SmartSpider):
    name = "vn_cafef"
    source_timezone = 'Asia/Ho_Chi_Minh'

    country_code = 'VNM'
    country = '越南'
    language = 'vi'
    allowed_domains = ["cafef.vn"]

    strict_date_required = True
    use_curl_cffi = True
    fallback_content_selector = "div.totalcontentdetail"

    dateparser_settings = {'DATE_ORDER': 'DMY'}

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "news_scraper.middlewares.CurlCffiMiddleware": 543,
            "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
        },
        "CURLL_CFFI_IMPERSONATE": "chrome120",
        "CONCURRENT_REQUESTS": 16,
        "DOWNLOAD_DELAY": 0.2
    }

    async def start(self):
        """Start with the first timeline page."""
        yield scrapy.Request(
            "https://cafef.vn/timelinelist/18836/1.chn",
            callback=self.parse,
            headers={"Referer": "https://cafef.vn/doanh-nghiep.chn"},
            dont_filter=True
        )

    def parse(self, response):
        """Parse AJAX timeline pages."""
        articles = response.xpath(
            '//div[contains(@class, "tlitem")] | //li[contains(@class, "tlitem")]'
        )

        has_valid_item_in_window = False

        for article in articles:
            link = article.xpath('.//h3/a/@href').get()
            if not link:
                continue
            if not link.startswith('http'):
                link = "https://cafef.vn" + link

            # URL date hint extraction: indices 3-8 of the numeric part
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
                headers={"Referer": "https://cafef.vn/doanh-nghiep.chn"},
                meta={"publish_time_hint": publish_time}
            )

        # Pagination with breaker
        if has_valid_item_in_window:
            current_page = 1
            page_match = re.search(r'/timelinelist/18836/(\d+)\.chn', response.url)
            if page_match:
                current_page = int(page_match.group(1))

            next_page = current_page + 1
            next_url = f"https://cafef.vn/timelinelist/18836/{next_page}.chn"
            yield scrapy.Request(
                next_url,
                callback=self.parse,
                    headers={"Referer": "https://cafef.vn/doanh-nghiep.chn"}
                )

    def parse_detail(self, response):
        """Parse article detail page."""
        item = self.auto_parse_item(
            response,
            title_xpath="//h1[contains(@class, 'title')]/text()",
            publish_time_xpath="//span[contains(@class, 'pdate')]/text()"
        )

        item['author'] = "CafeF"
        item['section'] = "Doanh nghiệp"

        yield item
