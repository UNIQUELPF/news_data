import scrapy
from datetime import datetime
from news_scraper.spiders.base_spider import BaseNewsSpider
import re

class TjKhovarSpider(BaseNewsSpider):
    name = 'tj_khovar'

    country_code = 'TJK'

    country = '塔吉克斯坦'
    allowed_domains = ['khovar.tj']
    start_urls = ['https://khovar.tj/category/economic/']
    
    # 数据库表名配置
    target_table = 'tj_khovar_news'
    
    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
    }
    
    # 塔吉克语月份映射
    MONTH_MAP = {
        'Январ': '01', 'Феврал': '02', 'Март': '03', 'Апрел': '04',
        'Май': '05', 'Июн': '06', 'Июл': '07', 'Август': '08',
        'Сентябр': '09', 'Октябр': '10', 'Ноябр': '11', 'Декабр': '12'
    }

    def parse(self, response):
        # 提取文章列表项
        articles = response.css('h2 a')
        for article in articles:
            link = article.css('::attr(href)').get()
            if link:
                yield response.follow(link, self.parse_article)

        # 翻页逻辑
        next_page = response.css('a.next.page-numbers::attr(href)').get()
        if next_page:
            yield response.follow(next_page, self.parse)

    def parse_article(self, response):
        # 1. 标题
        title = response.css('h1::text').get('').strip()
        if not title:
            return

        # 2. 发布时间解析
        # 格式示例: "Март 25, 2026 11:00"
        raw_date = response.css('div.author span.meta::text').get('').strip()
        if not raw_date:
            # 备选选择器
            raw_date = response.css('div.author::text').get('').strip()

        pub_time = self._parse_date(raw_date)
        
        # 3. 日期过滤断点
        if not self.filter_date(pub_time):
            self.logger.info(f"Filtered date: {pub_time} for {response.url}")
            return

        # 4. 正文提取
        paragraphs = response.css('.content-area p::text').getall()
        content = "\n\n".join([p.strip() for p in paragraphs if p.strip()])

        # 5. 作者/来源提取 
        author = 'AMIT «Ховар»'
        author_match = re.search(r'АМИТ «Ховар»', content)
        if author_match:
            author = 'AMIT «Ховар»'

        item = {
            'url': response.url,
            'title': title,
            'content': content,
            'publish_time': pub_time,
            'author': author,
            'language': 'tg', # 塔吉克语
            'section': 'Economic'
        }
        
        yield item

    def _parse_date(self, date_str):
        """解析塔吉克语格式日期字符串"""
        # "Март 25, 2026 11:00" -> "03 25, 2026 11:00"
        for tj_month, en_month in self.MONTH_MAP.items():
            if tj_month in date_str:
                date_str = date_str.replace(tj_month, en_month)
                break
        
        try:
            # 兼容格式: "03 25, 2026 11:00"
            return datetime.strptime(date_str, "%m %d, %Y %H:%M")
        except Exception:
            self.logger.warning(f"Date parsing failed for: {date_str}, using NOW")
            return datetime.now()
