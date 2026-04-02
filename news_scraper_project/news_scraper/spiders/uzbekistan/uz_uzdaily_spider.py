import scrapy
from datetime import datetime
from news_scraper.spiders.base_spider import BaseNewsSpider

class UzUzdailySpider(BaseNewsSpider):
    name = 'uz_uzdaily'
    allowed_domains = ['uzdaily.uz']
    
    # 类别 2 是综合新闻板块
    base_url = 'https://www.uzdaily.uz/ru/section/2/?page={}'
    start_urls = [base_url.format(1)]
    
    # 数据库配置 (Uzbekistan -> uz, Site -> uzdaily)
    target_table = 'uz_uzdaily_news'
    
    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'CONCURRENT_REQUESTS': 16,
        'DOWNLOAD_DELAY': 0.5,
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_TIMEOUT': 30
    }

    def parse(self, response):
        # 提取列表项
        articles = response.css('a.item_news_block')
        
        current_page = response.meta.get('page', 1)
        # 只要这一页存在文章块，就探测下一页 (解耦过滤计数与翻页)
        if articles:
            next_page = current_page + 1
            if next_page < 3000:
                yield scrapy.Request(
                    self.base_url.format(next_page),
                    callback=self.parse,
                    meta={'page': next_page}
                )
        
        for art in articles:
            link = art.css('::attr(href)').get()
            # 强化日期清洗: 处理可能存在的空格和换行符
            date_str = art.css('span.date::text').get()
            
            if not link:
                continue

            pub_time = None
            if date_str:
                date_str = date_str.strip()
                try:
                    # 尝试 DD/MM/YYYY 格式
                    pub_time = datetime.strptime(date_str, '%d/%m/%Y')
                except:
                    # 尝试 YYYY-MM-DD 格式
                    try: pub_time = datetime.fromisoformat(date_str[:10])
                    except: pass

            # 日期过滤
            if pub_time and not self.filter_date(pub_time):
                # 如果日期存在且早于 2026，跳过单篇文章
                continue
            
            yield response.follow(
                link, 
                self.parse_article, 
                meta={'pub_time': pub_time}
            )

    def parse_article(self, response):
        # 1. 提取标题
        title = response.css('h1::text, span.name::text').get('').strip()
        
        # 2. 提取日期 (优先使用 meta 传递，兜底使用 JSON-LD 或页面元数据)
        pub_time = response.meta.get('pub_time')
        if not pub_time:
            # 尝试 JSON-LD
            import json
            try:
                json_ld = response.xpath('//script[@type="application/ld+json"]/text()').get()
                if json_ld:
                    data = json.loads(json_ld)
                    if isinstance(data, list): data = data[0]
                    # 有的文章是列表，有的是单对象，取其中的 datePublished
                    for obj in (data if isinstance(data, list) else [data]):
                        if 'datePublished' in obj:
                            pub_time = datetime.fromisoformat(obj['datePublished'][:10])
                            break
            except: pass
        
        if not pub_time:
            pub_time = datetime.now()

        # 3. 日期过滤
        if not self.filter_date(pub_time):
            return

        # 4. 提取正文内容
        # UzDaily 详情页正文包装在 .text 或 .body 或 article 等容器中
        content_parts = response.css('div.text p::text, div.body p::text, div.content p::text').getall()
        content = "\n\n".join([p.strip() for p in content_parts if p.strip()])
        
        if not content or len(content) < 100:
            # 兜底：抓取全文本容器
            content = response.xpath('string(//div[contains(@id, "content")])').get()
            if not content:
                content = response.xpath('string(//article)').get()

        item = {
            'url': response.url,
            'title': title,
            'content': content,
            'publish_time': pub_time,
            'author': 'UzDaily.uz',
            'language': 'ru',
            'section': 'Economy & Society'
        }
        
        yield item
