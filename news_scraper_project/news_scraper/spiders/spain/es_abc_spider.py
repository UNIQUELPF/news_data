import scrapy
from datetime import datetime
import re
import json
from news_scraper.spiders.base_spider import BaseNewsSpider

class EsAbcSpider(BaseNewsSpider):
    name = 'es_abc'

    country_code = 'ESP'

    country = '西班牙'
    allowed_domains = ['abc.es']
    
    # 经济板块分页
    base_url = 'https://www.abc.es/economia/pagina-{}.html'
    start_urls = [base_url.format(1)]
    
    # 数据库配置 (Spain -> es, Site -> abc)
    target_table = 'es_abc_news'
    
    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'CONCURRENT_REQUESTS': 16,
        'DOWNLOAD_DELAY': 0.5,
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_TIMEOUT': 30
    }

    def parse(self, response):
        # 1. 提取文章链接
        # 链接格式: .../transporte-20260330200020-nt.html
        article_links = response.css('h2.v-a-t a::attr(href), a.v-a-t::attr(href)').getall()
        
        current_page = response.meta.get('page', 1)
        valid_items_count = 0
        
        for link in set(article_links):
            # 列表页日期拦截: 提取 URL 中的 8 位日期指纹
            date_match = re.search(r'-(\d{8})\d+-nt\.html$', link)
            if date_match:
                date_str = date_match.group(1)
                try:
                    pub_time = datetime.strptime(date_str, '%Y%m%d')
                except:
                    continue

                if not self.filter_date(pub_time):
                    continue
                
                valid_items_count += 1
                yield response.follow(
                    link, 
                    self.parse_article, 
                    meta={'pub_time': pub_time}
                )

        # 如果没抓到或者没有触发拦截，尝试更广泛的选择器 (针对首页大图)
        if valid_items_count == 0:
            for link in response.css('a[href*="-2026"]::attr(href)').getall():
                if '/economia/' in link:
                    valid_items_count += 1
                    yield response.follow(link, self.parse_article)

        # 翻页逻辑
        if valid_items_count > 0 and current_page < 1000:
            next_page = current_page + 1
            yield scrapy.Request(
                self.base_url.format(next_page),
                callback=self.parse,
                meta={'page': next_page}
            )

    def parse_article(self, response):
        # 1. 提取标题
        title = response.css('h1::text').get('').strip()
        
        # 2. 提取日期
        pub_time = response.meta.get('pub_time')
        if not pub_time:
            # 尝试 JSON-LD 
            try:
                scripts = response.xpath('//script[@type="application/ld+json"]/text()').getall()
                for s in scripts:
                    data = json.loads(s)
                    if isinstance(data, dict) and 'datePublished' in data:
                        pub_time = datetime.fromisoformat(data['datePublished'][:10])
                        break
            except: pass
            
        if not pub_time:
            pub_time = datetime.now()

        # 3. 日期过滤
        if not self.filter_date(pub_time):
            return

        # 4. 提取正文内容 (Vocento 核心类名适配)
        # ABC.es 的正文段落通常使用 span.v-fc__p 或 span[class*="v-p-"]
        content_parts = response.css('span.v-fc__p::text, span[class*="v-p-"]::text, .voc-p-c p::text').getall()
        content = "\n\n".join([p.strip() for p in content_parts if len(p.strip()) > 30])
        
        if not content:
            # 强化模式
            content = response.xpath('string(//div[@itemprop="articleBody"])').get()
            if not content:
                # 最后的兜底
                content = "\n\n".join(response.css('article p::text').getall())

        item = {
            'url': response.url,
            'title': title,
            'content': content,
            'publish_time': pub_time,
            'author': response.css('span.voc-a-n::text, .v-fc__a::text').get('ABC Economía').strip(),
            'language': 'es',
            'section': 'Economía'
        }
        
        yield item
