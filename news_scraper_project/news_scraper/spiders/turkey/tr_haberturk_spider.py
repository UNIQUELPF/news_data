import scrapy
import json
from datetime import datetime
from news_scraper.spiders.smart_spider import SmartSpider


class TrHaberturkSpider(SmartSpider):
    name = "tr_haberturk"
    source_timezone = 'Europe/Istanbul'

    country_code = 'TUR'
    country = '土耳其'
    language = 'tr'

    allowed_domains = ['haberturk.com']

    start_url = 'https://www.haberturk.com/ekonomi'

    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'CONCURRENT_REQUESTS': 8,
        'DOWNLOAD_DELAY': 1,
        'ROBOTSTXT_OBEY': False,
        "DOWNLOADER_MIDDLEWARES": {
            "news_scraper.middlewares.CurlCffiMiddleware": None,
        },
        "DOWNLOAD_HANDLERS": {
            "http": "scrapy.core.downloader.handlers.http11.HTTP11DownloadHandler",
            "https": "scrapy.core.downloader.handlers.http11.HTTP11DownloadHandler",
        },
    }

    use_curl_cffi = False
    strict_date_required = True
    fallback_content_selector = "article"

    async def start(self):
        yield scrapy.Request(self.start_url, callback=self.parse, dont_filter=True)

    def parse(self, response):
        links = response.css('a::attr(href)').getall()
        for link in sorted(set(links)):
            if '-ekonomi' not in link:
                continue
            if not any(char.isdigit() for char in link):
                continue
            yield response.follow(link, self.parse_detail)

    def parse_detail(self, response):
        # 1. JSON-LD 提取 (最精准)
        pub_time = None
        author = 'Haberturk'
        title_override = None

        for ld in response.css('script[type="application/ld+json"]::text').getall():
            try:
                data = json.loads(ld)
                if isinstance(data, list):
                    data = data[0]
                if '@graph' in data:
                    data = data['@graph'][0]

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

        # 2. 备选方案: HTML meta 提取 (如果 JSON-LD 缺失)
        if not pub_time:
            date_str = response.css('meta[property="article:published_time"]::attr(content)').get()
            if date_str:
                try:
                    pub_time = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                except Exception:
                    pass

        if not pub_time:
            return
        pub_time_utc = self.parse_to_utc(pub_time)

        # 3. SmartSpider 日期窗口 + 去重过滤
        if not self.should_process(response.url, pub_time_utc):
            return

        # 4. 自动提取 (ContentEngine)
        item = self.auto_parse_item(response)

        # 5. 用 JSON-LD 值覆盖关键字段
        if title_override:
            item['title'] = title_override
        item['publish_time'] = pub_time_utc
        item['author'] = author
        item['section'] = 'Ekonomi'

        yield item
