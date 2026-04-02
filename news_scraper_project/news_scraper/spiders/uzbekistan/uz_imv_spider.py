import scrapy
import json
from datetime import datetime
from news_scraper.spiders.base_spider import BaseNewsSpider

class UzImvSpider(BaseNewsSpider):
    name = 'uz_imv'
    allowed_domains = ['api.mf.uz', 'imv.uz', 'mf.uz']
    
    # API 列表入口
    start_urls = ['https://api.mf.uz/api/v1/site/post/list/?limit=12&offset=0&menu_slug=yangiliklar']
    
    # 详情 API 模板
    detail_api_tpl = 'https://api.mf.uz/api/v1/site/post/{slug}/'
    
    # 数据库表 (Uzbekistan -> uz, Site -> imv)
    target_table = 'uz_imv_news'
    
    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'CONCURRENT_REQUESTS': 16,
        'DOWNLOAD_DELAY': 0.2,
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_TIMEOUT': 40
    }

    def parse(self, response):
        try:
            data = json.loads(response.text)
        except Exception as e:
            self.logger.error(f"Failed to parse JSON list from {response.url}: {e}")
            return

        results = data.get('results', [])
        valid_items_on_page = 0
        
        for item in results:
            slug = item.get('slug')
            pub_date_str = item.get('pub_date') # 2026-03-05T17:03:00+05:00
            
            if not slug or not pub_date_str:
                continue

            # 日期转换
            try:
                # 只取 YYYY-MM-DD
                pub_time = datetime.fromisoformat(pub_date_str[:10])
            except:
                pub_time = datetime.now()

            # 日期过滤
            if not self.filter_date(pub_time):
                continue
            
            valid_items_on_page += 1
            # 请求详情 API 以获得完整正文
            detail_url = self.detail_api_tpl.format(slug=slug)
            yield scrapy.Request(
                detail_url, 
                callback=self.parse_article,
                meta={'pub_time': pub_time, 'origin_url': f"https://www.imv.uz/news/post/{slug}"}
            )

        # 翻页逻辑: 使用 API 返回的 next 分页链接
        next_url = data.get('next')
        if next_url and valid_items_on_page > 0:
            yield scrapy.Request(next_url, callback=self.parse)

    def parse_article(self, response):
        try:
            d_data = json.loads(response.text)
        except:
            return

        title = d_data.get('title', '').strip()
        # API 中 content 通常是带 HTML 标签的内容
        content_html = d_data.get('content', '') or d_data.get('body', '')
        
        # 简单清理 HTML
        import re
        content = re.sub(r'<[^>]+>', ' ', content_html)
        content = content.replace('&nbsp;', ' ').strip()

        pub_time = response.meta.get('pub_time')
        
        item = {
            'url': response.meta.get('origin_url', response.url),
            'title': title,
            'content': content,
            'publish_time': pub_time,
            'author': 'Ministry of Economy and Finance of Uzbekistan',
            'language': 'uz',
            'section': 'Yangiliklar'
        }
        
        yield item
