# 塞尔维亚danas爬虫，负责抓取对应站点、机构或栏目内容。

import scrapy
import re
from datetime import datetime
from news_scraper.spiders.smart_spider import SmartSpider


class DanasSpider(SmartSpider):
    name = 'danas'
    country_code = 'SRB'
    country = '塞尔维亚'
    language = 'sr'
    source_timezone = 'Europe/Belgrade'
    start_date = '2024-01-01'
    allowed_domains = ['danas.rs']
    fallback_content_selector = '.post-content'

    start_urls = [
        'https://www.danas.rs/vesti/ekonomija/',
        'https://www.danas.rs/rubrika/vesti/ekonomija/',
        'https://www.danas.rs/rubrika/svet/'
    ]

    # Serbian month mapping (genitive case)
    SR_MONTHS = {
        'januara': 1, 'februara': 2, 'marta': 3, 'aprila': 4,
        'maja': 5, 'juna': 6, 'jula': 7, 'avgusta': 8,
        'septembra': 9, 'oktobra': 10, 'novembra': 11, 'decembra': 12
    }

    def parse(self, response):
        """Parses the news list page."""
        headers = response.css('h3.article-post-title')
        self.logger.info(f"Scraping {len(headers)} articles from {response.url}")

        has_valid_item_in_window = False

        for header in headers:
            title_node = header.css('a')
            if not title_node:
                title_node = header if header.root.tag == 'a' else None

            if not title_node:
                continue

            title = title_node.xpath('string()').get().strip()
            href = title_node.css('::attr(href)').get()

            date_node = header.xpath('./preceding::span[contains(@class, "published")][1]')
            if not date_node:
                date_node = header.xpath('ancestor::article//span[contains(@class, "published")]')

            if date_node:
                date_str = date_node.xpath('string()').get().strip()
                date_str = date_str.replace('•', '').strip()
                publish_time = self.parse_sr_date(date_str)

                if publish_time and href:
                    article_url = response.urljoin(href)
                    if self.should_process(article_url, publish_time):
                        has_valid_item_in_window = True
                        yield scrapy.Request(
                            url=article_url,
                            callback=self.parse_detail,
                            meta={'title_hint': title, 'publish_time_hint': publish_time}
                        )

        # V2 断路器翻页
        if has_valid_item_in_window:
            next_page = response.css('a.next.page-numbers::attr(href)').get()
            if next_page:
                yield response.follow(next_page, callback=self.parse)

    def parse_sr_date(self, date_str):
        """Parses Serbian date strings like '05.03.2026. 15:20' or 'danas 10:36'."""
        now = datetime.now()
        try:
            if 'danas' in date_str.lower():
                time_match = re.search(r'(\d{2}):(\d{2})', date_str)
                if time_match:
                    return now.replace(hour=int(time_match.group(1)), minute=int(time_match.group(2)), second=0, microsecond=0)

            date_match = re.search(r'(\d{2})\.(\d{2})\.(\d{4})\.\s+(\d{2}):(\d{2})', date_str)
            if date_match:
                day = int(date_match.group(1))
                month = int(date_match.group(2))
                year = int(date_match.group(3))
                hour = int(date_match.group(4))
                minute = int(date_match.group(5))
                return datetime(year, month, day, hour, minute)

        except Exception as e:
            self.logger.error(f"Error parsing date {date_str}: {e}")
        return None

    def parse_detail(self, response):
        """Parses the article detail page."""
        item = self.auto_parse_item(
            response,
            title_xpath="//h1/text()",
        )
        item['author'] = 'Danas.rs'
        item['section'] = 'Vesti/Ekonomija'
        if item.get('content_plain') and len(item['content_plain']) > 50:
            yield item
