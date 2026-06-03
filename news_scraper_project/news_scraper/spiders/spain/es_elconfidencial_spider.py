import scrapy
from datetime import datetime
import re
import json
from news_scraper.spiders.smart_spider import SmartSpider

class EsElconfidencialSpider(SmartSpider):
    name = 'es_elconfidencial'
    source_timezone = 'Europe/Madrid'

    country_code = 'ESP'

    country = '西班牙'
    language = 'es'
    allowed_domains = ['elconfidencial.com']

    strict_date_required = True
    use_curl_cffi = False
    fallback_content_selector = ".newsType__content, .innerArticle__body, article"

    custom_settings = {
        'DOWNLOADER_MIDDLEWARES': {
            'news_scraper.middlewares.CurlCffiMiddleware': None,
        },
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.elconfidencial.com/',
        },
        'DOWNLOAD_HANDLERS': {
            'http': 'scrapy.core.downloader.handlers.http11.HTTP11DownloadHandler',
            'https': 'scrapy.core.downloader.handlers.http11.HTTP11DownloadHandler',
        },
        'CONCURRENT_REQUESTS': 16,
        'DOWNLOAD_DELAY': 0.5,
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_TIMEOUT': 40
    }

    async def start(self):
        # 实时新闻入口
        url = 'https://www.elconfidencial.com/ultima-hora-en-vivo/'
        yield scrapy.Request(url, callback=self.parse, dont_filter=True)

    def parse(self, response):
        articles = response.css('.lastMinuteEntry')
        self.logger.info(f"Found {len(articles)} articles on {response.url}")

        has_valid_item_in_window = False

        for article in articles:
            # 提取链接
            link_el = article.css('a::attr(href)').get()
            if not link_el:
                continue
            url = response.urljoin(link_el)

            # 优先从列表页 HTML 结构中提取时间
            date_str = article.css('.lastMinuteEntry__time::text').get()
            publish_time = self.parse_date(date_str.strip() if date_str else None)

            # 兜底：如果 HTML 没提取到日期，尝试从 URL 提取
            if not publish_time:
                date_match = re.search(r'/(\d{4})-(\d{2})-(\d{2})/', url)
                if date_match:
                    y, m, d = date_match.groups()
                    try:
                        publish_time = datetime(year=int(y), month=int(m), day=int(d))
                    except:
                        pass

            # SmartSpider 增量过滤闸口
            if not self.should_process(url, publish_time):
                continue

            has_valid_item_in_window = True
            yield response.follow(
                url,
                self.parse_detail,
                meta={'publish_time_hint': publish_time}
            )

        # 翻页逻辑：仅由窗口有效性与页面上“下一页”链接的实际存在性驱动
        # 该站点未在静态 HTML 中公开下一页链接（使用前端 JS 滚动加载），因此不进行硬编码翻页以防失控
        if has_valid_item_in_window:
            next_page = response.css('a.next::attr(href)').get()
            if next_page:
                yield response.follow(next_page, callback=self.parse, dont_filter=True)

    def parse_detail(self, response):
        item = self.auto_parse_item(response)
        item['author'] = response.css('span[class*="author"]::text, .signature__name::text').get('El Confidencial').strip()
        item['section'] = 'Última Hora'
        yield item
