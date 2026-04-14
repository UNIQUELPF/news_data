import scrapy
from datetime import datetime
from news_scraper.spiders.base_spider import BaseNewsSpider

class UzAnhorSpider(BaseNewsSpider):
    name = 'uz_anhor'

    country_code = 'UZB'

    country = '乌兹别克斯坦'
    allowed_domains = ['anhor.uz']
    
    # 经济新闻类别列表
    base_url = 'https://anhor.uz/category/economy/page/{}/'
    start_urls = [base_url.format(1)]
    
    # 数据库配置 (Uzbekistan -> uz, Site -> anhor)
    target_table = 'uz_anhor_news'
    
    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'CONCURRENT_REQUESTS': 16,
        'DOWNLOAD_DELAY': 0.5,
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_TIMEOUT': 30
    }

    def parse(self, response):
        # 根据探测，文章块通常在 posts-list 的子容器中
        # 每个块包含标题 posts-list__head 和日期 posts-list__date
        article_blocks = response.css('.posts-list .row > div, .posts-list__item')
        
        current_page = response.meta.get('page', 1)
        valid_items_count = 0
        
        for block in article_blocks:
            link = block.css('h3.posts-list__head a::attr(href)').get()
            date_str = block.css('span.posts-list__date::text').get()
            
            if not link:
                # 尝试更深一层的查找
                link = block.css('a.posts-list__head-link::attr(href)').get()
            
            if not link:
                continue

            # 日期转换 (DD.MM.YYYY)
            pub_time = None
            if date_str:
                try:
                    pub_time = datetime.strptime(date_str.strip(), '%d.%m.%Y')
                except: pass
            
            # 如果能判定日期且早于 2026，跳过
            if pub_time and not self.filter_date(pub_time):
                continue
            
            valid_items_count += 1
            yield response.follow(
                link, 
                self.parse_article, 
                meta={'pub_time': pub_time}
            )

        # 如果没抓到，尝试兼容其他布局 (针对可能的置顶大图)
        if valid_items_count == 0:
            for link in response.css('h2 a::attr(href), .entry-title a::attr(href)').getall():
                if '/news/' in link:
                    valid_items_count += 1
                    yield response.follow(link, self.parse_article)

        # 翻页逻辑: 只要当前页有最新数据，就继续往后翻
        if valid_items_count > 0 and current_page < 500:
            next_page = current_page + 1
            yield scrapy.Request(
                self.base_url.format(next_page),
                callback=self.parse,
                meta={'page': next_page}
            )

    def parse_article(self, response):
        # 1. 提取标题
        title = response.css('h1::text, .entry-title::text').get('').strip()
        
        # 2. 提取日期 (优先使用 meta 传递的日期)
        pub_time = response.meta.get('pub_time')
        if not pub_time:
            # 兜底从页面搜寻 DD.MM.YYYY
            import re
            match = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', response.text)
            if match:
                d, m, y = match.groups()
                try: pub_time = datetime(year=int(y), month=int(m), day=int(d))
                except: pass
        
        if not pub_time:
            pub_time = datetime.now()

        # 3. 日期过滤
        if not self.filter_date(pub_time):
            return

        # 4. 提取正文内容
        # 排除 sidebar, comment 等无关区域
        body_parts = response.css('div.entry-content p::text, div.content p::text, article p::text').getall()
        content = "\n\n".join([p.strip() for p in body_parts if p.strip()])
        
        if len(content) < 50:
            # 强化提取: 直接抓取文章主体容器
            content = response.xpath('string(//div[contains(@class, "entry-content")])').get()
            if not content:
                content = response.xpath('string(//article)').get()
        
        if content:
            content = content.replace('\t', '').replace('\r', '').strip()

        item = {
            'url': response.url,
            'title': title,
            'content': content,
            'publish_time': pub_time,
            'author': 'Anhor.uz Economy',
            'language': 'ru',
            'section': 'Economy'
        }
        
        yield item
