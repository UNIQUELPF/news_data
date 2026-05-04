import json
import re
from datetime import datetime, timedelta

import scrapy
from news_scraper.spiders.smart_spider import SmartSpider


class SinchewSpider(SmartSpider):
    name = "malaysia_sinchew"

    country_code = "MYS"
    country = "马来西亚"
    language = "zh"
    source_timezone = "Asia/Kuala_Lumpur"
    start_date = "2026-01-01"
    strict_date_required = False  # Dates unavailable on list API (relative time only)
    use_curl_cffi = True

    allowed_domains = ["sinchew.com.my"]

    # AJAX API endpoint for category posts
    # cat=3 for Finance (财经)
    API_URL = "https://www.sinchew.com.my/ajx-api/category_posts/?cat=3&page={page}&nooffset=false&editorialcat=0&posts_per_pages=10"

    fallback_content_selector = "div.article-page-content[itemprop='articleBody']"

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.0,
        'CONCURRENT_REQUESTS': 8,
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'X-Requested-With': 'XMLHttpRequest',
        }
    }

    def start_requests(self):
        yield scrapy.Request(
            self.API_URL.format(page=1),
            callback=self.parse_list,
            meta={'page': 1},
            dont_filter=True
        )

    def parse_list(self, response):
        page = response.meta['page']
        try:
            items = json.loads(response.text)
        except Exception as e:
            self.logger.error(f"Failed to parse JSON from page {page}: {e}")
            return

        if not items or not isinstance(items, list):
            self.logger.info(f"No more items or invalid JSON on page {page}")
            return

        self.logger.info(f"Page {page}: found {len(items)} items")

        has_valid_item_in_window = False

        for item_data in items:
            url = item_data.get('permalink')
            title = item_data.get('title')
            time_display = item_data.get('time_display', '')

            if not url:
                continue

            # Parse relative time to approximate datetime for window filtering
            publish_time_hint = self._parse_relative_time(time_display)

            if not self.should_process(url, publish_time_hint):
                continue

            has_valid_item_in_window = True
            yield scrapy.Request(
                url,
                callback=self.parse_detail,
                meta={
                    'title_hint': title,
                    'publish_time_hint': publish_time_hint,
                    'section_hint': 'Finance',
                }
            )

        # Pagination
        if has_valid_item_in_window and len(items) >= 10:
            next_page = page + 1
            if next_page <= 2000:
                yield scrapy.Request(
                    self.API_URL.format(page=next_page),
                    callback=self.parse_list,
                    meta={'page': next_page},
                    dont_filter=True
                )

    def parse_detail(self, response):
        item = self.auto_parse_item(
            response,
            title_xpath="//meta[@property='og:title']/@content",
            publish_time_xpath="//meta[@property='article:published_time']/@content",
        )

        # Clean title suffix (e.g., "Article Title - 星洲网")
        title = item.get('title')
        if title and ' - ' in title:
            item['title'] = title.split(' - ')[0].strip()

        # Fallback: if no publish_time from auto_parse, try span.time with "发布:" prefix
        if not item.get('publish_time'):
            time_text = response.css('span.time ::text').get()
            if time_text and '发布:' in time_text:
                match = re.search(r'(\d+:\d+[ap]m)\s+(\d+/\d+/\d+)', time_text)
                if match:
                    try:
                        t_str = f"{match.group(2)} {match.group(1)}"
                        dt = datetime.strptime(t_str, "%d/%m/%Y %I:%M%p")
                        item['publish_time'] = self.parse_to_utc(dt)
                    except Exception:
                        pass

        # Date filter (manual since strict_date_required=False)
        publish_time = item.get('publish_time')
        if publish_time and not self.full_scan:
            if publish_time < self.cutoff_date:
                self.logger.info(f"Reached date cutoff {self.cutoff_date} at {response.url}")
                return

        # Author
        item['author'] = response.css('meta[name="author"]::attr(content)').get() or "星洲网"
        item['section'] = response.meta.get('section_hint', 'Finance')

        yield item

    def _parse_relative_time(self, time_display):
        """Parse Chinese relative time display to approximate datetime.
        Examples: '18小时前', '2天前', '5分钟前', '刚刚'
        Returns a naive datetime, or None."""
        if not time_display:
            return None

        time_display = time_display.strip()
        now = datetime.now()

        # "刚刚" = just now
        if '刚刚' in time_display:
            return now

        # Pattern: number + unit + 前
        match = re.match(r'(\d+)\s*(分钟|小时|天|周|月|年)前', time_display)
        if match:
            num = int(match.group(1))
            unit = match.group(2)

            if '分钟' in unit:
                delta = timedelta(minutes=num)
            elif '小时' in unit:
                delta = timedelta(hours=num)
            elif '天' in unit:
                delta = timedelta(days=num)
            elif '周' in unit:
                delta = timedelta(weeks=num)
            elif '月' in unit:
                delta = timedelta(days=num * 30)
            elif '年' in unit:
                delta = timedelta(days=num * 365)
            else:
                return None

            return now - delta

        return None
