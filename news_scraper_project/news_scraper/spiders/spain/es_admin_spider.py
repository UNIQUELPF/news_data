import scrapy
from datetime import datetime
import re
from news_scraper.spiders.base_spider import BaseNewsSpider

class EsAdminSpider(BaseNewsSpider):
    name = 'es_admin'

    country_code = 'ESP'

    country = '西班牙'
    allowed_domains = ['administracion.gob.es', 'boe.es', 'interior.gob.es', 'sanidad.gob.es', 'moncloa.gob.es']
    
    # 列表页
    start_urls = ['https://administracion.gob.es/pag_Home/atencionCiudadana/Noticias.html']
    
    # 数据库配置 (Spain -> es, Site -> administracion)
    target_table = 'es_admin_news'

    def parse(self, response):
        # 1. 提取所有新闻链接项
        # 格式通常为: <a class="ppg-link-novedad" ...>31/03/2026: Procesos de...</a>
        news_items = response.css('a.ppg-link-novedad')
        
        valid_items_count = 0
        for item in news_items:
            link = item.css('::attr(href)').get()
            text = item.css('::text').get()
            if not link or not text:
                continue

            # 2. 提取日期: 格式为 DD/MM/YYYY
            date_match = re.search(r'(\d{2})/(\d{2})/(\d{4})', text)
            if not date_match:
                continue
                
            day, month, year = date_match.groups()
            try:
                pub_time = datetime(year=int(year), month=int(month), day=int(day))
            except ValueError:
                continue

            # 3. 日期过滤 (2026-01-01 之后)
            if not self.filter_date(pub_time):
                continue
            
            valid_items_count += 1
            # 提取标题 (冒号之后的部分)
            title = text.split(':', 1)[-1].strip() if ':' in text else text.strip()
            
            absolute_url = response.urljoin(link)
            yield scrapy.Request(
                absolute_url, 
                callback=self.parse_article,
                meta={'title': title, 'pub_time': pub_time}
            )

    def parse_article(self, response):
        title = response.meta.get('title')
        pub_time = response.meta.get('pub_time')
        
        content = ""
        url_str = response.url
        
        # 针对不同域名的内容提取策略
        if 'boe.es' in url_str:
            # BOE 官方公报
            content_parts = response.css('#DOdocText p::text, #DOdocText li::text').getall()
            content = "\n\n".join([p.strip() for p in content_parts if p.strip()])
        elif 'moncloa.gob.es' in url_str:
            # 首相府
            content_parts = response.css('div.c-content p::text, div.c-content li::text').getall()
            content = "\n\n".join([p.strip() for p in content_parts if p.strip()])
        else:
            # 通用政府站点提取逻辑
            content_parts = response.css('div.noticia-cuerpo p::text, div.content p::text, article p::text, div.text p::text').getall()
            content = "\n\n".join([p.strip() for p in content_parts if len(p.strip()) > 20])

        # 如果上述失败，采取激进提取
        if not content:
            content = "\n\n".join(response.xpath('//p//text()').getall())

        item = {
            'url': response.url,
            'title': title,
            'content': content,
            'publish_time': pub_time,
            'author': 'Administración del Estado',
            'language': 'es',
            'section': 'Noticias'
        }
        
        yield item
