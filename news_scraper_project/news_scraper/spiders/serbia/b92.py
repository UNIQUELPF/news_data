# 塞尔维亚b92爬虫，负责抓取对应站点、机构或栏目内容。

import scrapy
import re
from datetime import datetime
from news_scraper.spiders.smart_spider import SmartSpider


class B92Spider(SmartSpider):
    name = 'b92'
    country_code = 'SRB'
    country = '塞尔维亚'
    language = 'sr'
    source_timezone = 'Europe/Belgrade'
    start_date = '2024-01-01'
    allowed_domains = ['b92.net']
    start_urls = ['https://www.b92.net/najnovije-vesti']
    fallback_content_selector = '#article-content'

    custom_settings = {
        'ROBOTSTXT_OBEY': False
    }

    def parse(self, response):
        items = response.css('.news-item-data')

        has_valid_item_in_window = False

        for item in items:
            title_tag = item.css('h2.news-item-title a')
            url = title_tag.attrib.get('href')
            title = "".join(title_tag.css('span::text').getall()).strip()
            if not title:
                title = title_tag.css('::text').get().strip()

            date_str = item.css('.news-item-date::text').get()
            hour_str = item.css('.news-item-hour::text').get()

            if date_str and hour_str:
                publish_time = self.parse_sr_date(date_str.strip(), hour_str.strip())

                if publish_time and url:
                    full_url = response.urljoin(url)
                    if self.should_process(full_url, publish_time):
                        has_valid_item_in_window = True
                        yield scrapy.Request(
                            full_url,
                            callback=self.parse_detail,
                            meta={'title_hint': title, 'publish_time_hint': publish_time}
                        )

        # V2 断路器翻页
        if has_valid_item_in_window:
            next_page = response.css('ul.pagination li.page-item a.page-link[href*="page="]::attr(href)').getall()
            current_page_match = re.search(r'page=(\d+)', response.url)
            current_page = int(current_page_match.group(1)) if current_page_match else 1

            target_page = current_page + 1
            for link in next_page:
                if f"page={target_page}" in link:
                    yield response.follow(link, self.parse)
                    break

    def parse_detail(self, response):
        item = self.auto_parse_item(
            response,
            title_xpath="//meta[@property='og:title']/@content",
        )
        item['author'] = response.css('.article-author::text').get() or "B92"
        item['section'] = 'Vesti'
        if item.get('content_plain') and len(item['content_plain']) > 50:
            yield item

    def parse_sr_date(self, date_str, hour_str):
        """Parses Serbian date strings like 'dd.mm.yyyy.' + 'HH:MM'."""
        try:
            date_clean = date_str.rstrip('.')
            full_str = f"{date_clean} {hour_str}"
            return datetime.strptime(full_str, "%d.%m.%Y %H:%M")
        except Exception as e:
            self.logger.error(f"Error parsing date {date_str} {hour_str}: {e}")
            return None
