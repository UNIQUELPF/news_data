import scrapy
from bs4 import BeautifulSoup
from datetime import datetime
import json
import re
from news_scraper.spiders.base_spider import BaseNewsSpider

class BloombergSpider(BaseNewsSpider):
    name = 'jp_bloomberg'
    allowed_domains = ['bloomberg.com']
    start_urls = ['https://www.bloomberg.com/jp/economics']
    
    # 目标表名：jp_bloomberg_news
    target_table = 'jp_bloomberg_news'
    use_curl_cffi = True # 启用高效指纹浏览器模拟
    
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
        # 1. 模式 1: 解析 initialState JSON (最全)
        # 彭博社将数据直接存放在 JSON 脚本中
        scripts = response.xpath('//script[contains(text(), "initialState")]/text()').getall()
        found_links = []
        
        for script_text in scripts:
            try:
                # 尝试解析纯 JSON 字符串
                data = json.loads(script_text)
                # 深度遍历或根据 ID 搜索 (由 subagent 记录的结构: props.pageProps.initialState)
                def find_urls(obj):
                    if isinstance(obj, dict):
                        if 'url' in obj and isinstance(obj['url'], str) and '/news/articles/' in obj['url']:
                            url = response.urljoin(obj['url'])
                            if url not in self.scraped_urls:
                                self.scraped_urls.add(url)
                                found_links.append(url)
                        for v in obj.values():
                            find_urls(v)
                    elif isinstance(obj, list):
                        for item in obj:
                            find_urls(item)
                
                find_urls(data)
            except:
                pass

        # 2. 模式 2: 分页 API (深度回溯)
        # 彭博社的分页 API 每次请求 10 条
        for offset in range(10, 200, 10):
            api_url = f"https://www.bloomberg.com/lineup-next/api/paginate?id=story-list-1&page=jp-economics&offset={offset}&variation=archive&type=lineup_content&locale=ja"
            yield scrapy.Request(api_url, callback=self.parse_api_json)

        self.logger.info(f"Bloomberg List: Found {len(set(found_links))} initial article links.")
        
        for url in set(found_links):
            yield scrapy.Request(url, callback=self.parse_article)

    def parse_api_json(self, response):
        try:
            data = json.loads(response.text)
            # data root 通常包含 story-list-1
            items = []
            if 'story-list-1' in data:
                items = data['story-list-1'].get('items', [])
            else:
                # 兜底：深度搜索 items
                def find_items(obj):
                    if isinstance(obj, dict):
                        if 'items' in obj and isinstance(obj['items'], list):
                            return obj['items']
                        for v in obj.values():
                            res = find_items(v)
                            if res: return res
                    return None
                items = find_items(data) or []

            for item in items:
                if 'url' in item:
                    url = response.urljoin(item['url'])
                    if url not in self.scraped_urls:
                        self.scraped_urls.add(url)
                        yield scrapy.Request(url, callback=self.parse_article)
        except Exception as e:
            self.logger.error(f"Error parsing Bloomberg API JSON: {e}")

    def parse_article(self, response):
        self.logger.info(f"Parsing article: {response.url}")
        item = {}
        item['url'] = response.url
        
        # 1. 标题提取 (h1 结合 meta)
        title = response.css('h1::text').get() or \
                response.xpath('//meta[@property="og:title"]/@content').get()
        item['title'] = title.strip() if title else ''

        # 2. 正文提取 (使用浏览器探测到的精准选择器，配合 string(.) 递归提取)
        paragraph_nodes = response.css('p[data-component="paragraph"]') or \
                          response.css('div.body-copy p') or \
                          response.css('article p')
        
        paragraphs = [p.xpath('string(.)').get().strip() for p in paragraph_nodes if p.xpath('string(.)').get()]
        
        if paragraphs:
            item['content'] = "\n\n".join([p for p in paragraphs if len(p) > 30])
        else:
            item['content'] = ""

        # 3. 发布时间提取
        pub_time_str = response.xpath('//meta[@property="article:published_time"]/@content').get() or \
                       response.xpath('//meta[@name="parsely-pub-date"]/@content').get() or \
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
        item['author'] = 'Bloomberg'
        item['language'] = 'ja'
        item['section'] = 'Economics'

        if item.get('content') and len(item['content']) > 100:
            yield item
