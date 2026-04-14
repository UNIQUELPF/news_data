import scrapy
from datetime import datetime
from news_scraper.spiders.base_spider import BaseNewsSpider
import re

class TjAvestaSpider(BaseNewsSpider):
    name = 'tj_avesta'

    country_code = 'TJK'

    country = '塔吉克斯坦'
    allowed_domains = ['avesta.tj']
    start_urls = ['https://avesta.tj/news/ekonomika/']
    
    # 数据库表名配置
    target_table = 'tj_avesta_news'
    
    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
    }

    # 俄语月份映射
    RUS_MONTHS = {
        'января': '01', 'февраля': '02', 'марта': '03', 'апреля': '04',
        'мая': '05', 'июня': '06', 'июля': '07', 'августа': '08',
        'сентября': '09', 'октября': '10', 'ноября': '11', 'декабря': '12'
    }

    def parse(self, response):
        # 提取文章列表项
        articles = response.css('h3.jeg_post_title a')
        for article in articles:
            link = article.css('::attr(href)').get()
            if link:
                yield response.follow(link, self.parse_article)

        # 翻页逻辑
        next_page = response.css('a.page_nav.next::attr(href)').get()
        if next_page:
            yield response.follow(next_page, self.parse)

    def parse_article(self, response):
        # 1. 标题
        title = response.css('h1.jeg_post_title::text').get('').strip()
        if not title:
            return

        # 2. 发布时间解析
        # 格式示例: "31 марта, 2026 / 14:30"
        raw_date = response.css('div.jeg_meta_date a::text').get() or response.css('div.jeg_meta_date::text').get('')
        raw_date = raw_date.strip()
        
        pub_time = self._parse_date(raw_date)
        
        # 3. 日期过滤断点
        if not self.filter_date(pub_time):
            self.logger.info(f"Filtered date: {pub_time} for {response.url}")
            return

        # 4. 正文提取
        # 通常在 div.content-inner 或 div.jeg_inner_content p 中
        paragraphs = response.css('div.content-inner p::text').getall()
        if not paragraphs:
             paragraphs = response.css('div.jeg_inner_content p::text').getall()
             
        content = "\n\n".join([p.strip() for p in paragraphs if p.strip()])

        item = {
            'url': response.url,
            'title': title,
            'content': content,
            'publish_time': pub_time,
            'author': 'Avesta.tj',
            'language': 'ru', # 俄语
            'section': 'Economic'
        }
        
        yield item

    def _parse_date(self, date_str):
        """解析俄语格式日期字符串"""
        # "31 марта, 2026 / 14:30" -> "31 03, 2026 14:30"
        # 移除 '/' 并替换月份
        date_str = date_str.replace('/', ' ')
        for rus_m, num_m in self.RUS_MONTHS.items():
            if rus_m in date_str.lower():
                date_str = re.sub(rus_m, num_m, date_str, flags=re.IGNORECASE)
                break
        
        # 清理多余空格
        date_str = re.sub(r'\s+', ' ', date_str).strip()
        
        try:
            # 格式: "31 03, 2026 14:30"
            return datetime.strptime(date_str, "%d %m, %Y %H:%M")
        except Exception:
            self.logger.warning(f"Date parsing failed for: {date_str}, using NOW")
            return datetime.now()
