# 哈萨克斯坦informkz spider爬虫，负责抓取对应站点、机构或栏目内容。

import scrapy
from news_scraper.spiders.smart_spider import SmartSpider


class InformKzSpider(SmartSpider):
    name = 'informkz'

    country_code = 'KAZ'
    country = '哈萨克斯坦'
    language = 'ru'
    source_timezone = 'Asia/Almaty'
    dateparser_settings = {'languages': ['ru']}

    allowed_domains = ['inform.kz']
    fallback_content_selector = '.article__body-text'

    # 经济板块列表页
    base_url = 'https://www.inform.kz/category/ekonomika_s1?page={}'

    custom_settings = {
        'DOWNLOAD_DELAY': 1,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 2,
    }

    def start_requests(self):
        yield scrapy.Request(
            self.base_url.format(1),
            meta={
                'page': 1,
                'playwright': True,
                'playwright_include_page': False,
                'playwright_page_goto_kwargs': {
                    'wait_until': 'domcontentloaded',
                }
            },
            callback=self.parse_list,
            dont_filter=True
        )

    def parse_list(self, response):
        articles = response.css('a.news-card')
        if not articles:
            self.logger.info("No articles found on this page.")
            return

        has_valid_item_in_window = False

        for art in articles:
            link = art.css('::attr(href)').get()
            if not link:
                continue

            full_url = response.urljoin(link)

            # Extract date from link text (format: "09:16, 04 Май 2026 Title...")
            all_text = art.css('::text').getall()
            full_text = ''.join(all_text).strip()
            date_text = ''
            if all_text:
                date_text = all_text[0].strip()

            publish_time = self.parse_date(date_text)

            if not self.should_process(full_url, publish_time):
                continue

            has_valid_item_in_window = True

            # Title is the remainder of the link text after the date
            title_text = full_text
            if date_text and full_text.startswith(date_text):
                title_text = full_text[len(date_text):].strip()

            yield scrapy.Request(
                full_url,
                callback=self.parse_detail,
                dont_filter=True,
                meta={
                    'publish_time_hint': publish_time,
                    'title_hint': title_text,
                    'playwright': True,
                    'playwright_include_page': False,
                    'playwright_page_goto_kwargs': {
                        'wait_until': 'domcontentloaded',
                    }
                }
            )

        # Pagination with circuit breaker (no hardcoded page limit)
        if has_valid_item_in_window:
            current_page = response.meta.get('page', 1)
            next_page = current_page + 1
            yield scrapy.Request(
                self.base_url.format(next_page),
                callback=self.parse_list,
                dont_filter=True,
                meta={
                    'page': next_page,
                    'playwright': True,
                    'playwright_include_page': False,
                    'playwright_page_goto_kwargs': {
                        'wait_until': 'domcontentloaded',
                    }
                }
            )

    def parse_detail(self, response):
        item = self.auto_parse_item(
            response,
            title_xpath="//h1//text()",
        )

        if not self.should_process(response.url, item.get('publish_time')):
            return

        item['author'] = 'Inform.kz'
        item['section'] = 'Economy'

        yield item
