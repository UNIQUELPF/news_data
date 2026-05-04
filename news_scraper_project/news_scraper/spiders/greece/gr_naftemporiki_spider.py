import scrapy
from news_scraper.spiders.smart_spider import SmartSpider


class GrNaftemporikiSpider(SmartSpider):
    name = 'gr_naftemporiki'

    country_code = 'GRC'
    country = '希腊'
    language = 'el'
    source_timezone = 'Europe/Athens'
    use_curl_cffi = True

    # 列表页只有时间 (如 "14:04")，没有完整日期，所以不能做列表页日期过滤
    strict_date_required = False

    allowed_domains = ['naftemporiki.gr']

    # 航运报新闻大厅列表
    base_url = 'https://www.naftemporiki.gr/newsroom/page/{}/'

    fallback_content_selector = '.post-content'

    # 列表页无日期，无法做窗口断路，用最大翻页数作为安全阀
    max_pages = 500

    custom_settings = {
        'DOWNLOAD_DELAY': 0.5,
        'DOWNLOAD_TIMEOUT': 30,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 2,
    }

    def start_requests(self):
        yield scrapy.Request(
            self.base_url.format(1),
            callback=self.parse_list,
            meta={'page': 1},
            dont_filter=True
        )

    def parse_list(self, response):
        # HTML: <div class="box-item"> containing <div class="time"> and <div class="title">
        articles = response.css('div.box-item')

        has_valid_item_in_window = False

        for article in articles:
            url = article.css('div.title a::attr(href)').get()
            if not url:
                continue
            url = response.urljoin(url)

            title_hint = article.css('div.title a::text').get()

            # 列表页只有时间无完整日期，详情页 meta 标签有完整发布时间
            if not self.should_process(url):
                continue

            has_valid_item_in_window = True
            yield scrapy.Request(
                url,
                callback=self.parse_detail,
                meta={
                    'title_hint': title_hint,
                    'section_hint': 'News',
                }
            )

        current_page = response.meta['page']
        if has_valid_item_in_window and current_page < self.max_pages:
            next_page = current_page + 1
            yield scrapy.Request(
                self.base_url.format(next_page),
                callback=self.parse_list,
                meta={'page': next_page},
                dont_filter=True
            )

    def parse_detail(self, response):
        item = self.auto_parse_item(
            response,
            title_xpath="//h1//text()",
            publish_time_xpath="//meta[@property='article:published_time']/@content",
        )

        item['author'] = 'Naftemporiki Newsroom'
        item['section'] = response.meta.get('section_hint', 'News')

        yield item
