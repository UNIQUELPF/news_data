import scrapy
import json
from datetime import datetime
from news_scraper.spiders.smart_spider import SmartSpider


class TrSabahSpider(SmartSpider):
    name = "tr_sabah"
    source_timezone = 'Europe/Istanbul'

    country_code = 'TUR'
    country = '土耳其'
    language = 'tr'

    allowed_domains = ['sabah.com.tr']

    # 初始 URL: 经济新闻列表
    base_url = 'https://www.sabah.com.tr/ekonomi/{}'

    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'CONCURRENT_REQUESTS': 8,
        'DOWNLOAD_DELAY': 1,
        'ROBOTSTXT_OBEY': False,
    }

    use_curl_cffi = True
    strict_date_required = True
    fallback_content_selector = ".newsDetailText"

    async def start(self):
        yield scrapy.Request('https://www.sabah.com.tr/ekonomi', callback=self.parse, meta={'page': 1})

    def parse(self, response):
        # 提取文章链接
        links = response.css('a[href*="/ekonomi/"]::attr(href)').getall()

        has_valid_item_in_window = False

        for link in set(links):
            # 过滤掉纯分页和导航链接
            if link.strip('/').isdigit() or link == '/ekonomi':
                continue
            if '-' in link:
                has_valid_item_in_window = True
                yield response.follow(link, self.parse_detail)

        # Pagination breaker: 仅当当前页有有效链接时继续翻页
        if has_valid_item_in_window:
            current_page = response.meta.get('page', 1)
            next_page = current_page + 1
            yield scrapy.Request(
                self.base_url.format(next_page),
                callback=self.parse,
                meta={'page': next_page},
            )

    def parse_detail(self, response):
        # 1. JSON-LD 提取 (最可靠)
        pub_time = None
        author = 'Sabah'
        title_override = None

        for ld in response.css('script[type="application/ld+json"]::text').getall():
            try:
                data = json.loads(ld)
                if isinstance(data, list):
                    data = data[0]

                if not title_override:
                    title_override = data.get('headline') or data.get('name')

                ds = data.get('datePublished')
                if ds and not pub_time:
                    pub_time = datetime.fromisoformat(ds.replace('Z', '+00:00'))

                if 'author' in data:
                    auth_data = data['author']
                    if isinstance(auth_data, dict):
                        author = auth_data.get('name', author)
            except Exception:
                continue

        # 2. 备选方案: 标准 HTML 提取
        if not pub_time:
            date_str = response.css('meta[property="article:published_time"]::attr(content)').get()
            if date_str:
                try:
                    pub_time = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                except Exception:
                    pass

        pub_time_utc = self.parse_to_utc(pub_time) if pub_time else self.parse_to_utc(datetime.now())

        # 3. SmartSpider 日期窗口 + 去重过滤
        if not self.should_process(response.url, pub_time_utc):
            return

        # 4. 自动提取 (ContentEngine)
        item = self.auto_parse_item(response)

        # 5. 用 JSON-LD 值覆盖
        if title_override:
            item['title'] = title_override
        item['publish_time'] = pub_time_utc
        item['author'] = author
        item['section'] = 'Ekonomi'

        yield item
