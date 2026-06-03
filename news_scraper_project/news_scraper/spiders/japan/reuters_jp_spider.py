import json
import re
import urllib.parse

import scrapy
from scrapy_playwright.page import PageMethod
from news_scraper.spiders.smart_spider import SmartSpider


class ReutersJPSpider(SmartSpider):
    """Reuters Japan 爬虫（V2）。

    抓取站点：https://jp.reuters.com
    抓取栏目：economy
    入库表：jp_reuters_news
    语言：日语
    """

    name = 'reuters_jp'

    country_code = 'JPN'
    country = '日本'
    language = 'ja'
    source_timezone = 'Asia/Tokyo'

    allowed_domains = ['jp.reuters.com']
    start_urls = ['https://jp.reuters.com/economy/']

    strict_date_required = False
    fallback_content_selector = '[data-testid^="paragraph-"]'

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 2.0,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 1,
        'PLAYWRIGHT_LAUNCH_OPTIONS': {
            'headless': True,
            'timeout': 60000,
        },
    }

    async def start(self):
        js_scroll = """
        async () => {
            for (let i = 0; i < 5; i++) {
                window.scrollBy(0, window.innerHeight * 2);
                await new Promise(r => setTimeout(r, 1500));
            }
        }
        """
        for url in self.start_urls:
            yield scrapy.Request(
                url,
                callback=self.parse_listing,
                dont_filter=True,
                meta={
                    "playwright": True,
                    "playwright_page_methods": [
                        PageMethod("wait_for_load_state", "domcontentloaded"),
                        PageMethod("evaluate", js_scroll),
                        PageMethod("wait_for_timeout", 2000),
                    ],
                }
            )

    def parse_listing(self, response):
        """解析首页 JSON 嵌入数据及已滚动 DOM 提取文章链接。"""
        found_urls = set()

        # 1. 尝试从初始页面嵌入的 window.Fusion.globalContent 提取
        scripts = response.xpath(
            '//script[contains(text(), "window.Fusion.globalContent")]/text()'
        ).get()
        if scripts:
            try:
                json_text = re.search(
                    r'window\.Fusion\.globalContent\s*=\s*({.*?});', scripts
                )
                if json_text:
                    data = json.loads(json_text.group(1))
                    articles = data.get('result', {}).get('articles', [])
                    for art in articles:
                        url = response.urljoin(art.get('canonical_url'))
                        pub_time = self._extract_api_date(art)
                        if self.should_process(url, pub_time):
                            found_urls.add((url, pub_time))
            except Exception:
                pass

        # 2. 尝试从 DOM a 标签提取
        links = response.xpath(
            "//a[contains(@href, '/world/') or contains(@href, '/business/') or "
            "contains(@href, '/markets/') or contains(@href, '/economy/') or "
            "contains(@href, '/sports/')]/@href"
        ).getall()
        for link in links:
            url = response.urljoin(link)
            if '/economy/' in url or '/world/' in url or '/business/' in url or '/markets/' in url:
                if self.should_process(url):
                    found_urls.add((url, None))

        self.logger.info(
            f"Reuters JP List: Found {len(found_urls)} unique article links after scroll & JSON."
        )

        for url, pub_time in found_urls:
            yield scrapy.Request(
                url,
                callback=self.parse_article,
                meta={'publish_time_hint': pub_time, "playwright": True},
                dont_filter=self.full_scan,
            )

    def parse_article(self, response):
        """使用 auto_parse_item 自动提取文章元数据与正文。"""
        item = self.auto_parse_item(
            response,
            title_xpath="//h1/text()",
            publish_time_xpath="//meta[@property='article:published_time']/@content",
        )

        item['author'] = 'Reuters Japan'
        item['section'] = 'Economy'

        if item.get('content_plain') and len(item['content_plain']) > 100:
            yield item

    @staticmethod
    def _extract_api_date(article: dict):
        """从 API 返回的文章对象中提取发布时间。"""
        for field in ('display_date', 'publish_date', 'created_date', 'first_publish_date'):
            val = article.get(field)
            if val:
                return val
        return None
