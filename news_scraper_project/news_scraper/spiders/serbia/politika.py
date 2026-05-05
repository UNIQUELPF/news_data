# 塞尔维亚politika爬虫，负责抓取对应站点、机构或栏目内容。

import scrapy
from datetime import datetime
from news_scraper.spiders.smart_spider import SmartSpider


class PolitikaSpider(SmartSpider):
    name = 'politika'
    country_code = 'SRB'
    country = '塞尔维亚'
    language = 'sr'
    source_timezone = 'Europe/Belgrade'
    start_date = '2024-01-01'
    allowed_domains = ['politika.rs']
    start_urls = ['https://www.politika.rs/scc/columns/archive/6']
    fallback_content_selector = '#text-holder'

    custom_settings = {
        'ROBOTSTXT_OBEY': False
    }

    def parse(self, response):
        items = response.css('.column-data .news-item')

        has_valid_item_in_window = False

        for item in items:
            title_tag = item.css('h3.h3 a')
            url = title_tag.attrib.get('href')
            title = title_tag.css('::text').get().strip()

            if url:
                full_url = response.urljoin(url)
                # 列表页没有日期，直接通过详情页 should_process 过滤
                has_valid_item_in_window = True
                yield scrapy.Request(
                    full_url,
                    callback=self.parse_detail,
                    meta={'title_hint': title}
                )

        # V2 断路器翻页
        if has_valid_item_in_window:
            current_page_num = response.meta.get('page', 1)
            next_page_num = current_page_num + 1
            next_url = f"https://www.politika.rs/scc/columns/archive/6/page:{next_page_num}?url="
            yield scrapy.Request(
                next_url,
                callback=self.parse,
                meta={'page': next_page_num}
            )

    def parse_detail(self, response):
        publish_time_str = response.css('span[itemprop="datePublished"]::attr(content)').get()

        publish_time = None
        if publish_time_str:
            try:
                dt_str = publish_time_str.split('+')[0]
                publish_time = datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S")
            except Exception as e:
                self.logger.error(f"Error parsing date {publish_time_str}: {e}")

        item = self.auto_parse_item(
            response,
            title_xpath="//meta[@property='og:title']/@content",
        )
        if publish_time:
            item['publish_time'] = publish_time

        item['author'] = response.css('.article-author::text, .article-info .bold::text').get() or "Politika"
        item['section'] = 'Kolumne'

        if item.get('content_plain') and len(item['content_plain']) > 50:
            if self.should_process(response.url, item.get('publish_time')):
                yield item
