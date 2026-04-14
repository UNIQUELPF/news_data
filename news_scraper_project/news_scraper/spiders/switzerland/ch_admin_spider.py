import scrapy
import json
from datetime import datetime
from news_scraper.spiders.base_spider import BaseNewsSpider

class ChAdminSpider(BaseNewsSpider):
    name = 'ch_admin'

    country_code = 'CHE'

    country = '瑞士'
    allowed_domains = ['news.admin.ch', 'admin.ch', 'www.news.admin.ch']
    
    # 国家代码 + 网站
    target_table = 'ch_admin_news'
    use_curl_cffi = True
    
    # 必要的请求头
    custom_settings = {
        'DEFAULT_REQUEST_HEADERS': {
            'Origin': 'https://www.news.admin.ch',
            'Referer': 'https://www.news.admin.ch/',
            'Accept': 'application/json, text/plain, */*',
        }
    }

    def start_requests(self):
        # 构造符合服务器要求的 URL
        # start_date: 2026-01-01T00:00:00.000Z
        # end_date: 2026-12-31T23:59:59.999Z (涵盖整个2026年)
        self.base_api = "https://d-nsbc-p.admin.ch/v1/search"
        params = (
            "languages=en"
            "&newsKinds=CONTENT_HUB"
            "&newsKinds=ONSB"
            "&start_date=2026-01-01T00:00:00.000Z"
            "&end_date=2026-12-31T23:59:59.999Z"
            "&limit=12"
            "&sort=DESC"
        )
        url = f"{self.base_api}?{params}&offset=0"
        yield scrapy.Request(url=url, callback=self.parse_api)

    def parse_api(self, response):
        try:
            data = json.loads(response.text)
        except Exception as e:
            self.logger.error(f"Failed to parse JSON from {response.url}: {e}")
            return

        items_list = data.get('items', [])
        
        if not items_list:
            return

        for entry in items_list:
            article_id = entry.get('id')
            # 详情页逻辑：如果存在 externalUrl 则跳转，否则使用 ID 拼接
            url = entry.get('externalUrl')
            if not url:
                url = f"https://www.news.admin.ch/en/newnsb/{article_id}"
            
            # 日期过滤：使用 publishDate
            pub_date_str = entry.get('publishDate', '')
            if pub_date_str:
                try:
                    pub_date = datetime.fromisoformat(pub_date_str.replace('Z', '+00:00'))
                    if not self.filter_date(pub_date):
                        continue
                except:
                    pass

            yield scrapy.Request(url, callback=self.parse_article, meta={'entry': entry}, dont_filter=True)

        # 分页逻辑
        current_offset = int(response.url.split('offset=')[1].split('&')[0])
        next_offset = current_offset + 12
        
        # 保持原始参数结构
        next_url = response.url.replace(f"offset={current_offset}", f"offset={next_offset}")
        yield scrapy.Request(next_url, callback=self.parse_api)

    def parse_article(self, response):
        entry = response.meta.get('entry', {})
        
        item = {}
        item['url'] = response.url
        item['title'] = entry.get('title') or response.css('h1::text').get('').strip()
        
        # 提取发布时间
        pub_date_str = entry.get('publishDate', '')
        if pub_date_str:
            item['publish_time'] = pub_date_str.split('T')[0]
        else:
            item['publish_time'] = datetime.now().strftime('%Y-%m-%d')

        # 提取正文内容 - 兼容多种可能出现的 Nuxt 渲染后的标志性结构
        # 1. 导语
        lead = response.css('p.hero__description::text').get('').strip()
        
        # 2. 主体容器 (通常是这个类)
        content_nodes = response.css('div.container__center--xs.vertical-spacing p, div.container__center--xs.vertical-spacing h2, div.container__center--xs.vertical-spacing li')
        
        # 如果主体容器没中，尝试通用结构
        if not content_nodes:
            content_nodes = response.css('section.section--default p, section.section--default h2')
            
        body_text = "\n".join([n.css('::text').get('').strip() for n in content_nodes if n.css('::text').get()])
        
        item['content'] = (lead + "\n\n" + body_text).strip()
        
        # 备选：如果还是没抓到，尝试从 content 对象的描述信息中兜底
        if not item['content'] and entry.get('content', {}).get('metadata', {}).get('description'):
            item['content'] = entry['content']['metadata']['description']

        item['author'] = 'Swiss Federal News Service'
        item['country_code'] = 'CH'
        item['language'] = 'en'
        item['section'] = 'Federal Government'

        if len(item['content']) > 5 or item['title']:
            yield item
