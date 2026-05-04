import scrapy
from news_scraper.spiders.smart_spider import SmartSpider


class MetiSpider(SmartSpider):
    name = 'jp_meti'

    country_code = 'JPN'
    country = '日本'
    language = 'ja'
    source_timezone = 'Asia/Tokyo'
    use_curl_cffi = True

    start_date = '2026-01-01'
    fallback_content_selector = 'div.main.w1000, div#main'

    dateparser_settings = {'LANGUAGES': ['ja']}

    allowed_domains = ['meti.go.jp']
    start_urls = ['https://www.meti.go.jp/press/index.html']

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.0,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 2,
    }

    def start_requests(self):
        # 1. 抓取当前主页
        yield scrapy.Request(
            'https://www.meti.go.jp/press/index.html',
            callback=self.parse_list_ul,
            dont_filter=True,
        )

        # 2. 抓取 2026 年各月存档 (回溯至 2026-01-01)
        for month in ['01', '02', '03']:
            archive_url = f'https://www.meti.go.jp/press/archive_2026{month}.html'
            yield scrapy.Request(
                archive_url,
                callback=self.parse_list_ul,
                dont_filter=True,
            )

    def parse_list_ul(self, response):
        has_valid_item_in_window = False

        # Pattern 1: ul.clearfix.float_li structure (archive pages)
        items = response.css('ul.clearfix.float_li li')
        for li in items:
            date_str = li.css('div.txt_box p::text').get()
            link = li.css('div.txt_box a.cut_txt::attr(href)').get()

            if not link:
                continue

            url = response.urljoin(link)
            publish_time = self.parse_date(date_str) if date_str else None

            if not self.should_process(url, publish_time):
                continue

            has_valid_item_in_window = True
            yield scrapy.Request(
                url,
                callback=self.parse_detail,
                dont_filter=True,
                meta={
                    'title_hint': li.css('div.txt_box a.cut_txt::text').get(),
                    'publish_time_hint': publish_time,
                },
            )

        # Pattern 2: dl#release_menulist structure (main index page)
        dls = response.css('dl#release_menulist')
        if dls:
            dts = dls.css('dt')
            dds = dls.css('dd')
            for dt, dd in zip(dts, dds):
                date_str = dt.css('::text').get()
                link = dd.css('a::attr(href)').get()
                if not link:
                    continue

                url = response.urljoin(link)
                publish_time = self.parse_date(date_str) if date_str else None

                if not self.should_process(url, publish_time):
                    continue

                has_valid_item_in_window = True
                yield scrapy.Request(
                    url,
                    callback=self.parse_detail,
                    dont_filter=True,
                    meta={
                        'title_hint': dd.css('a::text').get(),
                        'publish_time_hint': publish_time,
                    },
                )

        if not has_valid_item_in_window:
            self.logger.info(
                f"All items on {response.url} are outside the window or already scraped. "
                "Stopping (no pagination on this page type)."
            )

    def parse_detail(self, response):
        item = self.auto_parse_item(
            response,
            title_xpath="//h1//text()",
        )

        if not self.should_process(response.url, item.get('publish_time')):
            return

        item['author'] = 'METI Japan'
        item['language'] = 'ja'
        item['section'] = 'Press Release'

        yield item
