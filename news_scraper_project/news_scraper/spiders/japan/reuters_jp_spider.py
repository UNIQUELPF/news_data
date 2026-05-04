import json
import re
import urllib.parse

import scrapy
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

    use_curl_cffi = True
    strict_date_required = False
    fallback_content_selector = '[data-testid^="paragraph-"]'

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 2.0,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 1,
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
            'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
        },
    }

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing, dont_filter=True)

    def parse_listing(self, response):
        """解析首页 JSON 嵌入数据并触发 API 分页请求。"""
        # 1. 模式 1: 初始页面嵌入的 window.Fusion.globalContent
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
                        if not self.should_process(url, pub_time):
                            continue
                        yield scrapy.Request(
                            url,
                            callback=self.parse_article,
                            meta={'publish_time_hint': pub_time},
                        )
            except Exception:
                pass

        # 2. 模式 2: API 分页（偏移量从 28 开始，首屏约 28 条）
        for offset in range(28, 500, 20):
            query_obj = {
                "arc-site": "reuters-japan",
                "fetch_type": "collection",
                "offset": offset,
                "section_id": "/economy/",
                "size": 20,
                "website": "reuters-japan",
            }
            query_str = urllib.parse.quote(json.dumps(query_obj))
            api_url = (
                "https://jp.reuters.com/pf/api/v3/content/fetch/"
                f"articles-by-section-alias-or-id-v1?query={query_str}"
            )
            yield scrapy.Request(api_url, callback=self.parse_api, dont_filter=True)

    def parse_api(self, response):
        """解析 API 分页响应并产出文章请求。"""
        try:
            data = json.loads(response.text)
            articles = data.get('result', {}).get('articles', [])
            for art in articles:
                url = response.urljoin(art.get('canonical_url'))
                pub_time = self._extract_api_date(art)
                if not self.should_process(url, pub_time):
                    continue
                yield scrapy.Request(
                    url,
                    callback=self.parse_article,
                    meta={'publish_time_hint': pub_time},
                )
        except Exception:
            pass

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
