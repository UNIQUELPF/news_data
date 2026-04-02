import scrapy
from bs4 import BeautifulSoup
from datetime import datetime
import json
import re
from news_scraper.spiders.base_spider import BaseNewsSpider

class ReutersJPSpider(BaseNewsSpider):
    name = 'jp_reuters'
    allowed_domains = ['jp.reuters.com']
    start_urls = ['https://jp.reuters.com/economy/']
    
    # 目标表名：jp_reuters_news
    target_table = 'jp_reuters_news'
    use_curl_cffi = True # 重要：处理路透社反爬
    
    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 2.0,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 1,
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
            'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
        }
    }


    def parse(self, response):
        # 1. 模式 1: 初始页面数据 (解析 window.Fusion.globalContent)
        scripts = response.xpath('//script[contains(text(), "window.Fusion.globalContent")]/text()').get()
        if scripts:
            try:
                # 提取 JSON 部分
                json_text = re.search(r'window\.Fusion\.globalContent\s*=\s*({.*?});', scripts)
                if json_text:
                    data = json.loads(json_text.group(1))
                    articles = data.get('result', {}).get('articles', [])
                    for art in articles:
                        url = response.urljoin(art.get('canonical_url'))
                        if url not in self.scraped_urls:
                            self.scraped_urls.add(url)
                            yield scrapy.Request(url, callback=self.parse_article)
            except:
                pass

        # 2. 模式 2: 分页 API (深度回溯至 2026-01-01)
        # 偏移量从 28 开始 (首屏通常有 28 条)
        for offset in range(28, 500, 20):
            query_obj = {
                "arc-site": "reuters-japan",
                "fetch_type": "collection",
                "offset": offset,
                "section_id": "/economy/",
                "size": 20,
                "website": "reuters-japan"
            }
            import urllib.parse
            query_str = urllib.parse.quote(json.dumps(query_obj))
            api_url = f"https://jp.reuters.com/pf/api/v3/content/fetch/articles-by-section-alias-or-id-v1?query={query_str}"
            yield scrapy.Request(api_url, callback=self.parse_api_json)

    def parse_api_json(self, response):
        try:
            data = json.loads(response.text)
            articles = data.get('result', {}).get('articles', [])
            for art in articles:
                url = response.urljoin(art.get('canonical_url'))
                if url not in self.scraped_urls:
                    self.scraped_urls.add(url)
                    yield scrapy.Request(url, callback=self.parse_article)
        except:
            pass

    def parse_article(self, response):
        item = {}
        item['url'] = response.url
        
        # 1. 标题提取 (h1 或 meta)
        title = response.css('h1::text').get() or \
                response.xpath('//meta[@property="og:title"]/@content').get()
        item['title'] = title.strip() if title else ''

        # 2. 正文提取
        # 路透社正文通常在 [data-testid^="paragraph-"]
        paragraphs = response.css('[data-testid^="paragraph-"]::text').getall() or \
                     response.css('p::text').getall()
        
        if paragraphs:
            item['content'] = "\n\n".join([p.strip() for p in paragraphs if len(p.strip()) > 20])
        else:
            item['content'] = ""

        # 3. 发布时间提取
        pub_time_str = response.xpath('//meta[@property="article:published_time"]/@content').get() or \
                       response.xpath('//meta[@name="article:published_time"]/@content').get() or \
                       response.css('time::attr(datetime)').get()
        
        pub_time = datetime.now()
        if pub_time_str:
            try:
                from dateutil import parser
                pub_time = parser.parse(pub_time_str).replace(tzinfo=None)
            except:
                pass

        # 4. 日期过滤 (2026-01-01)
        if not self.filter_date(pub_time):
            return

        item['publish_time'] = pub_time
        item['author'] = 'Reuters Japan'
        item['language'] = 'ja'
        item['section'] = 'Economy'

        if item.get('content') and len(item['content']) > 100:
            yield item
