import scrapy
from news_scraper.spiders.smart_spider import SmartSpider


class KapitalSpider(SmartSpider):
    name = 'kapital'

    country_code = 'KAZ'
    country = '哈萨克斯坦'
    language = 'ru'
    source_timezone = 'Asia/Almaty'

    allowed_domains = ['kapital.kz']
    fallback_content_selector = 'article'

    # Categories to crawl
    CATEGORIES = [
        {'name': 'economic', 'path': 'economic'},
        {'name': 'finance', 'path': 'finance'},
        {'name': 'investments', 'path': 'project/investments'},
        {'name': 'business', 'path': 'business'},
        {'name': 'technology', 'path': 'tehnology'},
    ]

    async def start(self):
        for cat in self.CATEGORIES:
            url = f"https://kapital.kz/{cat['path']}"
            yield scrapy.Request(
                url,
                callback=self.parse_list,
                meta={'cat_name': cat['name'], 'page': 1},
                dont_filter=True,
            )

    def parse_list(self, response):
        if self._stop_pagination:
            return
        cat_name = response.meta['cat_name']
        page = response.meta['page']

        articles = response.css('article')
        if not articles:
            self.logger.info(f"No articles found for {cat_name} on page {page}")
            return

        has_valid_item_in_window = False

        for art in articles:
            link_el = art.css('a::attr(href)').get()
            if not link_el:
                continue

            full_url = response.urljoin(link_el)

            # Extract date from <time> element
            time_el = art.css('time::attr(datetime)').get()
            if not time_el:
                time_el = art.css('time::text').get()
            publish_time = self.parse_date(time_el) if time_el else None

            if not self.should_process(full_url, publish_time):
                continue

            has_valid_item_in_window = True

            title_text = art.css('h2 a::text, h3 a::text, a::text').get()
            if title_text:
                title_text = title_text.strip()

            yield scrapy.Request(
                full_url,
                callback=self.parse_detail,
                meta={
                    'title_hint': title_text,
                    'publish_time_hint': publish_time,
                    'section_hint': cat_name,
                },
                dont_filter=self.full_scan,
            )

        # Continue pagination
        if has_valid_item_in_window:
            next_page = page + 1
            base_url = response.url.split('?')[0]
            next_url = f"{base_url}?page={next_page}"
            yield scrapy.Request(
                next_url,
                callback=self.parse_list,
                meta={'cat_name': cat_name, 'page': next_page},
                dont_filter=True,
            )

    def parse_detail(self, response):
        item = self.auto_parse_item(
            response,
            title_xpath="//h1/text()",
            publish_time_xpath="//time/@datetime",
        )
        item['author'] = 'Kapital.kz'
        item['section'] = response.meta.get('section_hint', 'economic')

        if not self.should_process(response.url, item.get('publish_time')):
            self._stop_pagination = True
            return

        yield item
