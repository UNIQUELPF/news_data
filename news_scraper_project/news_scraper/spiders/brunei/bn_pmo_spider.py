import scrapy
from datetime import datetime
from news_scraper.spiders.base_spider import BaseNewsSpider

class BnPmoSpider(BaseNewsSpider):
    name = 'bn_pmo'

    country_code = 'BRN'

    country = '文莱'
    allowed_domains = ['pmo.gov.bn']
    
    # 列表页入口
    base_url = 'https://www.pmo.gov.bn/1149-2/page/{}/?et_blog'
    start_urls = [base_url.format(1)]
    
    # 数据库表名配置 (Brunei -> bn, Site -> pmo)
    target_table = 'bn_pmo_news'
    
    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'CONCURRENT_REQUESTS': 8,
        'DOWNLOAD_DELAY': 1,
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_TIMEOUT': 30
    }

    def parse(self, response):
        # 提取文章详情链接 (通常在 article 标签内)
        articles = response.css('article')
        current_page = response.meta.get('page', 1)
        
        valid_items_on_page = 0
        for art in articles:
            link = art.css('a::attr(href)').get()
            if link:
                valid_items_on_page += 1
                yield response.follow(link, self.parse_article)

        # 翻页逻辑
        if valid_items_on_page > 0 and current_page < 500:
            next_page = current_page + 1
            yield scrapy.Request(
                self.base_url.format(next_page),
                callback=self.parse,
                meta={'page': next_page}
            )

    def parse_article(self, response):
        # 1. 提取标题
        title = response.css('h1::text, h1.entry-title::text').get('').strip()
        
        # 2. 提取发布日期
        pub_time = None
        # 针对 WordPress 全 HTML 搜索 DD/MM/YYYY
        import re
        content_text = response.text
        match = re.search(r'(\d{2})/(\d{2})/(\d{4})', content_text)
        if match:
            d, m, y = match.groups()
            try:
                pub_time = datetime(year=int(y), month=int(m), day=int(d))
            except: pass

        # 兜底: 尝试从页面文本聚合中发现
        if not pub_time:
            all_text = "".join(response.css('::text').getall())
            match_v2 = re.search(r'(\d{2})/(\d{2})/(\d{4})', all_text)
            if match_v2:
                d, m, y = match_v2.groups()
                try:
                    pub_time = datetime(year=int(y), month=int(m), day=int(d))
                except: pass

        if not pub_time:
            # 备选: URL 中的 uploads 路径带有日期
            img_match = re.search(r'/uploads/(\d{4})/(\d{2})/', response.text)
            if img_match:
                y, m = img_match.groups()
                pub_time = datetime(year=int(y), month=int(m), day=1)

        if not pub_time:
            pub_time = datetime.now()

        # 3. 日期过滤
        if not self.filter_date(pub_time):
            return

        # 4. 提取正文内容
        # 针对 WordPress 内容容器
        content_parts = response.css('div.entry-content p::text, div.post-content p::text, div.et_pb_module_inner p::text').getall()
        content = "\n\n".join([p.strip() for p in content_parts if p.strip()])
        
        # 兜底清理
        if not content:
            content = response.xpath('string(//div[contains(@class, "entry-content")])').get()
            if not content:
                content = response.xpath('string(//div[contains(@class, "post-content")])').get()

        item = {
            'url': response.url,
            'title': title,
            'content': content,
            'publish_time': pub_time,
            'author': 'Prime Minister\'s Office Brunei',
            'language': 'en',
            'section': 'Messages'
        }
        
        yield item
