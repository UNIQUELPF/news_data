import scrapy
import json
from datetime import datetime
from news_scraper.spiders.base_spider import BaseNewsSpider

class ThThairathSpider(BaseNewsSpider):
    name = 'th_thairath'
    allowed_domains = ['thairath.co.th']
    
    # 初始 URL：政治新闻最新列表
    base_url = 'https://www.thairath.co.th/news/politic/all-latest?filter=1&page={}'
    start_urls = [base_url.format(1)]
    
    # 数据库表名配置
    target_table = 'th_thairath_news'
    
    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'CONCURRENT_REQUESTS': 8,
        'DOWNLOAD_DELAY': 1
    }

    def parse(self, response):
        # 1. 尝试从 __NEXT_DATA__ 提取列表（最稳健）
        next_data_script = response.css('script#__NEXT_DATA__::text').get()
        if next_data_script:
            try:
                data = json.loads(next_data_script)
                # 遍历可能的路径
                # 路径 1: props.pageProps.initialState.common.data.items
                # 路径 2: props.initialState.common.data.items
                props = data.get('props', {})
                page_props = props.get('pageProps', {})
                initial_state = page_props.get('initialState') or props.get('initialState', {})
                
                items = initial_state.get('common', {}).get('data', {}).get('items', [])
                if items:
                    for item in items:
                        path = item.get('fullPath')
                        if path:
                            # 拼接完整链接
                            url = response.urljoin(path)
                            yield scrapy.Request(url, self.parse_article)
            except Exception as e:
                self.logger.error(f"Error parsing __NEXT_DATA__ in listing: {e}")

        # 2. 备选：从 HTML 提取链接（如果 JSON 结构改变）
        if not next_data_script:
            # 链接通常在 a[href^="/news/politic/"]
            links = response.css('a[href*="/news/politic/"]::attr(href)').getall()
            for link in set(links):
                # 过滤掉非文章链接（如列表页自身）
                if any(char.isdigit() for char in link.split('/')[-1]):
                    yield response.follow(link, self.parse_article)

        # 3. 翻页处理
        current_page = response.meta.get('page', 1)
        # 这里的翻页我们根据日期过滤，只要还有 2026/1/1 之后的数据就继续
        if current_page < 500: # 获取 500 页以覆盖历史
            next_page = current_page + 1
            yield scrapy.Request(
                self.base_url.format(next_page),
                callback=self.parse,
                meta={'page': next_page}
            )

    def parse_article(self, response):
        # 1. 优先使用 __NEXT_DATA__
        next_data_script = response.css('script#__NEXT_DATA__::text').get()
        if next_data_script:
            try:
                data = json.loads(next_data_script)
                props = data.get('props', {})
                page_props = props.get('pageProps', {})
                initial_state = page_props.get('initialState') or props.get('initialState', {})
                
                # 获取文章详情
                content_data = initial_state.get('content', {}).get('data', {}).get('items', {})
                if not content_data:
                    # 某些页面结构可能不同
                    content_data = initial_state.get('common', {}).get('data', {}).get('items', [{}])[0]

                title = content_data.get('title', '').strip()
                pub_time_str = content_data.get('publishTime', '')
                content_html = content_data.get('content', '')
                
                # 时间转换
                if pub_time_str:
                    pub_time = datetime.fromisoformat(pub_time_str.replace('Z', '+00:00'))
                else:
                    pub_time = datetime.now()

                # 2. 日期过滤
                if not self.filter_date(pub_time):
                    return

                # 清洗正文 (保留 HTML 标签转文本或直接处理)
                # 这里简单提取文本
                from scrapy.selector import Selector
                sel = Selector(text=content_html)
                content = "\n\n".join([p.strip() for p in sel.css('p::text, div::text').getall() if p.strip()])

                item = {
                    'url': response.url,
                    'title': title,
                    'content': content,
                    'publish_time': pub_time,
                    'author': content_data.get('author') or 'Thairath',
                    'language': 'th', # 泰叻报主要是泰语
                    'section': 'Politic'
                }
                yield item
                return # 成功解析 JSON 则退出
            except Exception as e:
                self.logger.error(f"Error parsing __NEXT_DATA__ in article {response.url}: {e}")

        # 3. 备选方案：标准 HTML 提取
        title = response.css('h1::text').get('').strip()
        pub_time_str = response.css('meta[property="article:published_time"]::attr(content)').get()
        if pub_time_str:
            pub_time = datetime.fromisoformat(pub_time_str.replace('Z', '+00:00'))
        else:
            pub_time = datetime.now()

        if not self.filter_date(pub_time):
            return

        paragraphs = response.css('.entry-content p::text, .detail p::text').getall()
        content = "\n\n".join([p.strip() for p in paragraphs if p.strip()])

        item = {
            'url': response.url,
            'title': title,
            'content': content,
            'publish_time': pub_time,
            'author': 'Thairath',
            'language': 'th',
            'section': 'Politic'
        }
        yield item
