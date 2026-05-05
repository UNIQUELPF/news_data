import json
import re
from datetime import datetime

import scrapy
from news_scraper.spiders.smart_spider import SmartSpider


class UzImvSpider(SmartSpider):
    name = "uz_imv"
    source_timezone = "Asia/Tashkent"

    country_code = "UZB"
    country = "乌兹别克斯坦"
    language = "uz"

    allowed_domains = ["api.mf.uz", "imv.uz", "mf.uz"]

    # 详情 API 模板
    detail_api_tpl = "https://api.mf.uz/api/v1/site/post/{slug}/"

    custom_settings = {
        "USER_AGENT": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "CONCURRENT_REQUESTS": 16,
        "DOWNLOAD_DELAY": 0.2,
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_TIMEOUT": 40,
    }

    use_curl_cffi = True
    fallback_content_selector = None  # API-based spider, no HTML content to parse
    strict_date_required = True

    async def start(self):
        """Initial requests entry point."""
        yield scrapy.Request(
            "https://api.mf.uz/api/v1/site/post/list/?limit=12&offset=0&menu_slug=yangiliklar",
            callback=self.parse,
            dont_filter=True,
        )

    def parse(self, response):
        """Parse JSON list API response."""
        try:
            data = json.loads(response.text)
        except Exception as e:
            self.logger.error(
                f"Failed to parse JSON list from {response.url}: {e}"
            )
            return

        results = data.get("results", [])
        has_valid_item_in_window = False

        for item in results:
            slug = item.get("slug")
            pub_date_str = item.get("pub_date")  # e.g. 2026-03-05T17:03:00+05:00

            if not slug or not pub_date_str:
                continue

            # 日期转换 (取 YYYY-MM-DD) -> UTC
            pub_time = None
            try:
                dt_obj = datetime.strptime(pub_date_str[:10], "%Y-%m-%d")
                pub_time = self.parse_to_utc(dt_obj)
            except Exception:
                pass

            detail_url = self.detail_api_tpl.format(slug=slug)
            origin_url = f"https://www.imv.uz/news/post/{slug}"

            # Panic Break: API 返回了条目但无有效日期，终止翻页
            if pub_time is None:
                self.logger.error(
                    f"STRICT STOP: No date found for {detail_url}. Terminating spider."
                )
                return

            if not self.should_process(origin_url, pub_time):
                continue

            has_valid_item_in_window = True
            yield scrapy.Request(
                detail_url,
                callback=self.parse_detail,
                meta={"pub_time": pub_time, "origin_url": origin_url},
            )

        # 翻页: 使用 API 返回的 next 分页链接
        next_url = data.get("next")
        if next_url and has_valid_item_in_window:
            yield scrapy.Request(next_url, callback=self.parse)

    def parse_detail(self, response):
        """Parse JSON detail API response (auto_parse_item not applicable for JSON)."""
        try:
            d_data = json.loads(response.text)
        except Exception:
            return

        title = d_data.get("title", "").strip()
        # API 中 content 通常是带 HTML 标签的内容
        content_html = d_data.get("content", "") or d_data.get("body", "")

        # 清理 HTML
        content = re.sub(r"<[^>]+>", " ", content_html)
        content = content.replace("&nbsp;", " ").strip()

        pub_time = response.meta.get("pub_time")

        item = {
            "url": response.meta.get("origin_url", response.url),
            "title": title,
            "content": content,
            "publish_time": pub_time,
            "author": "Ministry of Economy and Finance of Uzbekistan",
            "language": "uz",
            "section": "Yangiliklar",
        }

        yield item
