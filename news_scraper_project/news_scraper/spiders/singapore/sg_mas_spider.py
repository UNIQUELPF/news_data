import scrapy
from datetime import datetime
import json
from news_scraper.spiders.smart_spider import SmartSpider


class SgMasSpider(SmartSpider):
    name = "sg_mas"
    country_code = 'SGP'
    country = '新加坡'
    language = 'en'
    source_timezone = 'Asia/Singapore'
    start_date = '2024-01-01'
    allowed_domains = ["mas.gov.sg"]
    fallback_content_selector = '.mas-rte-content'

    api_url = "https://www.mas.gov.sg/api/v1/search?q=*:*&fq=mas_mastercontenttypes_sm:%22News%22&sort=mas_date_tdt%20desc&start={}&rows=20&json.nl=map"

    use_curl_cffi = True

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "news_scraper.middlewares.CurlCffiMiddleware": 543,
            "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
        },
        "CURLL_CFFI_IMPERSONATE": "chrome120",
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1
    }

    def start_requests(self):
        yield scrapy.Request(self.api_url.format(0), meta={"start": 0})

    def parse(self, response):
        try:
            data = json.loads(response.text)
            docs = data.get("response", {}).get("docs", [])
            start_val = response.meta.get("start", 0)
            self.logger.info(f"MAS API: Found {len(docs)} docs at start={start_val}")
        except Exception as e:
            self.logger.error(f"Failed to parse MAS API: {e}")
            return

        if not docs:
            return

        valid_items_in_page = 0
        for doc in docs:
            path = doc.get("page_url_s")
            date_str = doc.get("mas_date_tdt")

            if not path or not date_str:
                continue

            try:
                pub_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except Exception:
                continue

            # Make naive for SmartSpider comparison
            if pub_date.tzinfo:
                pub_date = pub_date.replace(tzinfo=None)

            if self.should_process(path, pub_date):
                valid_items_in_page += 1
                yield response.follow(
                    path,
                    self.parse_article,
                    meta={"publish_time_hint": pub_date}
                )

        # 只要当前页有在时间窗口内的文章，继续翻页
        if valid_items_in_page > 0:
            next_start = response.meta.get("start", 0) + 20
            yield scrapy.Request(
                self.api_url.format(next_start),
                callback=self.parse,
                meta={"start": next_start},
                dont_filter=True
            )

    def parse_article(self, response):
        item = self.auto_parse_item(
            response,
            title_xpath="//h1/text()",
        )
        item['author'] = "Monetary Authority of Singapore (MAS)"
        item['section'] = response.url.split("/")[4] if len(response.url.split("/")) > 4 else "Finance"
        if item.get('content_plain') and len(item['content_plain']) > 50:
            yield item
