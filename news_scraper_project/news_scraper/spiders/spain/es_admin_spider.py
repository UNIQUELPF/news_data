import scrapy
from datetime import datetime
import re
from news_scraper.spiders.smart_spider import SmartSpider

class EsAdminSpider(SmartSpider):
    name = 'es_admin'
    source_timezone = 'Europe/Madrid'

    country_code = 'ESP'

    country = '西班牙'
    language = 'es'
    allowed_domains = ['administracion.gob.es', 'boe.es', 'interior.gob.es', 'sanidad.gob.es', 'moncloa.gob.es']

    strict_date_required = True
    use_curl_cffi = True
    fallback_content_selector = "div.noticia-cuerpo, .content, article"

    async def start(self):
        yield scrapy.Request(
            'https://administracion.gob.es/pag_Home/atencionCiudadana/Noticias.html',
            callback=self.parse,
            dont_filter=True
        )

    def parse(self, response):
        # 1. 提取所有新闻链接项
        # 格式通常为: <a class="ppg-link-novedad" ...>31/03/2026: Procesos de...</a>
        news_items = response.css('a.ppg-link-novedad')
        has_valid_item_in_window = False

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

            absolute_url = response.urljoin(link)
            if not self.should_process(absolute_url, pub_time):
                continue

            has_valid_item_in_window = True
            # 提取标题 (冒号之后的部分)
            title = text.split(':', 1)[-1].strip() if ':' in text else text.strip()

            yield scrapy.Request(
                absolute_url,
                callback=self.parse_detail,
                meta={'title_hint': title, 'publish_time_hint': pub_time}
            )

    def parse_detail(self, response):
        item = self.auto_parse_item(response)

        # 针对不同域名的内容提取覆盖
        url_str = response.url
        if not item.get('content_plain'):
            content_parts = []
            if 'boe.es' in url_str:
                content_parts = response.css('#DOdocText p::text, #DOdocText li::text').getall()
            elif 'moncloa.gob.es' in url_str:
                content_parts = response.css('div.c-content p::text, div.c-content li::text').getall()
            else:
                content_parts = response.css('div.noticia-cuerpo p::text, div.content p::text, article p::text, div.text p::text').getall()
            if content_parts:
                item['content_plain'] = "\n\n".join([p.strip() for p in content_parts if len(p.strip()) > 20])

        item['author'] = 'Administración del Estado'
        item['section'] = 'Noticias'

        yield item
