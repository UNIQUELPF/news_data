import scrapy
import json
from datetime import datetime
from news_scraper.spiders.base_spider import BaseNewsSpider

class TjPresidentSpider(BaseNewsSpider):
    name = 'tj_president'
    allowed_domains = ['president.tj', 'controlpanel.president.tj']
    
    # 初始 API：从第 1 页开始
    base_list_url = 'https://controlpanel.president.tj/api/home-event?event_type=news&lang_id=3&page={}'
    start_urls = [base_list_url.format(1)]
    
    # 数据库表名配置
    target_table = 'tj_president_news'

    def parse(self, response):
        try:
            data = json.loads(response.text)
            items = data.get('data', [])
        except Exception as e:
            self.logger.error(f"Failed to parse List JSON: {e}")
            return

        if not items:
            self.logger.info("No more items found on this page.")
            return

        for item in items:
            news_id = item.get('id')
            if news_id:
                # 构建详情页 API URL
                detail_url = f'https://controlpanel.president.tj/api/event/show?type=news&id={news_id}&lang_id=3'
                yield scrapy.Request(detail_url, self.parse_article, meta={'news_id': news_id})

        # 翻页处理
        current_page = response.meta.get('page', 1)
        next_page = current_page + 1
        
        # 即使不知道总页数，API 如果返回空列表我们也会在开头 return
        # 我们进行一个相对合理的限制，防止无限爬取（配合日期过滤）
        if current_page < 1000: # 假设最多 1000 页
            yield scrapy.Request(
                self.base_list_url.format(next_page),
                callback=self.parse,
                meta={'page': next_page}
            )

    def parse_article(self, response):
        try:
            json_data = json.loads(response.text)
            detail = json_data.get('data', {})
        except Exception as e:
            self.logger.error(f"Failed to parse Detail JSON: {e}")
            return

        title = detail.get('title', '').strip()
        pub_date_str = detail.get('publish_date', '')
        
        try:
            # 格式: "2026-03-31 10:00:00"
            pub_date = datetime.strptime(pub_date_str, "%Y-%m-%d %H:%M:%S")
        except:
            pub_date = datetime.now()

        # 3. 日期过滤断点
        if not self.filter_date(pub_date):
            self.logger.info(f"Filtered date: {pub_date} for ID {response.meta.get('news_id')}")
            return

        content = detail.get('text', '').strip()
        
        item = {
            'url': f"https://www.president.tj/event/news/{response.meta.get('news_id')}",
            'title': title,
            'content': content,
            'publish_time': pub_date,
            'author': 'President.tj',
            'language': 'en',
            'section': 'News'
        }
        
        yield item
