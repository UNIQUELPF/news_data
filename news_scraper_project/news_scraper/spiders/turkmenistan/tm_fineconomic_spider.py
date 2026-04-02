import scrapy
from datetime import datetime
from news_scraper.spiders.base_spider import BaseNewsSpider

class TmFineconomicSpider(BaseNewsSpider):
    name = 'tm_fineconomic'
    allowed_domains = ['fineconomic.gov.tm']
    
    # 列表页入口
    base_url = 'https://fineconomic.gov.tm/news/all?page={}'
    start_urls = [base_url.format(1)]
    
    # 数据库表名配置 (Turkmenistan -> tm, Site -> fineconomic)
    target_table = 'tm_fineconomic_news'
    
    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'CONCURRENT_REQUESTS': 8,
        'DOWNLOAD_DELAY': 1,
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_TIMEOUT': 30
    }

    def parse(self, response):
        # 提取 habar 详情链接
        links = response.css('a[href*="/habar/"]::attr(href)').getall()
        current_page = response.meta.get('page', 1)
        
        valid_links_on_page = 0
        for link in set(links):
            # 这里的 URL 通常长这样: /habar/xxx-19.03.2026
            # 我们可以提前从 URL 提取日期进行粗筛
            url_date = None
            try:
                # 截取末尾 10 位: DD.MM.YYYY
                date_str = link.rstrip('/').split('-')[-1]
                if '.' in date_str and len(date_str) == 10:
                    url_date = datetime.strptime(date_str, '%d.%m.%Y')
            except:
                pass
            
            # 如果能确认为 2026 之前的数据，直接跳过 (URL 预过滤)
            if url_date and not self.filter_date(url_date):
                continue

            valid_links_on_page += 1
            yield response.follow(link, self.parse_article)

        # 翻页逻辑: 只要当前页有符合日期要求的链接，就继续翻页
        if valid_links_on_page > 0 and current_page < 1000:
            next_page = current_page + 1
            yield scrapy.Request(
                self.base_url.format(next_page),
                callback=self.parse,
                meta={'page': next_page}
            )

    def parse_article(self, response):
        # 1. 提取标题
        title = response.css('div.in-news__content--title::text').get('').strip()
        if not title:
            title = response.css('h1::text').get('').strip()
        
        # 2. 提取日期
        pub_time = None
        date_str = response.css('div.in-news__content--date::text').get('').strip()
        if date_str:
            try:
                # 格式: 19.03.2026
                pub_time = datetime.strptime(date_str, '%d.%m.%Y')
            except Exception as e:
                self.logger.warning(f"Date parsing failed for {response.url}: {e}")

        if not pub_time:
            # Fallback to URL parsing
            try:
                ds = response.url.rstrip('/').split('-')[-1]
                pub_time = datetime.strptime(ds, '%d.%m.%Y')
            except:
                pub_time = datetime.now()

        # 3. 日期过滤
        if not self.filter_date(pub_time):
            return

        # 4. 提取正文内容
        # 针对 in-news__content--text 容器
        body_parts = response.css('div.in-news__content--text p::text, div.in-news__content--text ::text').getall()
        content = "\n\n".join([p.strip() for p in body_parts if p.strip()])
        
        # 兜底清理: 如果内容太短，尝试直接抓取文本节点
        if len(content) < 50:
            content = response.xpath('string(//div[contains(@class, "in-news__content--text")])').get()
            if content:
                content = content.replace('\r', '').replace('\t', '').strip()

        item = {
            'url': response.url,
            'title': title,
            'content': content,
            'publish_time': pub_time,
            'author': 'Ministry of Finance and Economy of Turkmenistan',
            'language': 'tm',
            'section': 'Economics'
        }
        
        yield item
