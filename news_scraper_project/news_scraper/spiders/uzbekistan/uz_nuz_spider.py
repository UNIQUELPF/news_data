import re
from datetime import datetime

import scrapy
from news_scraper.spiders.smart_spider import SmartSpider


class UzNuzSpider(SmartSpider):
    name = "uz_nuz"
    source_timezone = "Asia/Tashkent"

    country_code = "UZB"
    country = "乌兹别克斯坦"
    language = "ru"

    allowed_domains = ["nuz.uz"]

    # 政治板块入口
    base_url = "https://nuz.uz/category/politika/page/{}/"

    custom_settings = {
        "USER_AGENT": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "CONCURRENT_REQUESTS": 4,
        "DOWNLOAD_DELAY": 0.5,
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_TIMEOUT": 30,
    }

    use_curl_cffi = True
    fallback_content_selector = ".td-post-content"
    strict_date_required = True

    async def start(self):
        """Initial requests entry point."""
        yield scrapy.Request(
            self.base_url.format(1), callback=self.parse, dont_filter=True
        )

    def parse(self, response):
        if self._stop_pagination:
            return
        # 提取链接，靠 URL 中 /YYYY/MM/DD/ 模式提取日期
        links = response.css("a::attr(href)").getall()

        current_page = response.meta.get("page", 1)
        has_valid_item_in_window = False

        for link in set(links):
            # 正则匹配日期指纹: /2026/03/26/
            date_match = re.search(r"/(\d{4})/(\d{2})/(\d{2})/", link)
            if not date_match:
                continue

            y, m, d = date_match.groups()
            try:
                dt_obj = datetime(year=int(y), month=int(m), day=int(d))
                pub_time = self.parse_to_utc(dt_obj)
            except Exception:
                continue

            # URL 匹配到日期模式时 pub_time 一定有效，无需 panic break
            if not self.should_process(link, pub_time):
                continue

            has_valid_item_in_window = True
            yield response.follow(
                link,
                self.parse_detail,
                meta={"publish_time_hint": pub_time},
            )

        # 翻页逻辑
        if has_valid_item_in_window:
            next_page = current_page + 1
            yield scrapy.Request(
                self.base_url.format(next_page),
                callback=self.parse,
                meta={"page": next_page},
            )

    def parse_detail(self, response):
        """Parse article detail page using SmartSpider auto extraction."""
        item = self.auto_parse_item(
            response,
            title_xpath="//h1[contains(@class, 'entry-title')]/text() | //h1/text()",
        )

        item["author"] = "News Uzbekistan (Nuz.uz)"
        item["section"] = "Politics"

        yield item
