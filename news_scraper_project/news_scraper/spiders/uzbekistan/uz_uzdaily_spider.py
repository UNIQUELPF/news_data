from datetime import datetime

import scrapy
from news_scraper.spiders.smart_spider import SmartSpider


class UzUzdailySpider(SmartSpider):
    name = "uz_uzdaily"
    source_timezone = "Asia/Tashkent"

    country_code = "UZB"
    country = "乌兹别克斯坦"
    language = "ru"

    allowed_domains = ["uzdaily.uz"]

    # 类别 2 是综合新闻板块
    base_url = "https://www.uzdaily.uz/ru/section/2/?page={}"

    custom_settings = {
        "USER_AGENT": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "CONCURRENT_REQUESTS": 16,
        "DOWNLOAD_DELAY": 0.5,
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_TIMEOUT": 30,
    }

    use_curl_cffi = True
    fallback_content_selector = ".text"
    strict_date_required = True

    async def start(self):
        """Initial requests entry point."""
        yield scrapy.Request(
            self.base_url.format(1), callback=self.parse, dont_filter=True
        )

    def parse(self, response):
        # 提取列表项
        articles = response.css("a.item_news_block")

        current_page = response.meta.get("page", 1)
        has_valid_item_in_window = False

        for art in articles:
            link = art.css("::attr(href)").get()
            date_str = art.css("span.date::text").get()

            if not link:
                continue

            # 强化日期清洗: DD/MM/YYYY 或 YYYY-MM-DD
            pub_time = None
            if date_str:
                date_str = date_str.strip()
                if date_str:
                    try:
                        dt_obj = datetime.strptime(date_str, "%d/%m/%Y")
                        pub_time = self.parse_to_utc(dt_obj)
                    except ValueError:
                        try:
                            dt_obj = datetime.fromisoformat(date_str[:10])
                            pub_time = self.parse_to_utc(dt_obj)
                        except Exception:
                            pass

            # Panic Break: 有链接但无日期，说明页面结构变化，终止翻页
            if pub_time is None:
                self.logger.error(
                    f"STRICT STOP: No date found for {link}. Terminating spider."
                )
                return

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
            title_xpath="//h1/text() | //*[contains(@class, 'name')]/text()",
        )

        item["author"] = "UzDaily.uz"
        item["section"] = "Economy & Society"

        yield item
