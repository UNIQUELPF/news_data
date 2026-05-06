import scrapy
from datetime import datetime
import re
import json
from news_scraper.spiders.smart_spider import SmartSpider

class EsAbcSpider(SmartSpider):
    name = 'es_abc'
    source_timezone = 'Europe/Madrid'

    country_code = 'ESP'

    country = '西班牙'
    language = 'es'
    allowed_domains = ['abc.es']

    strict_date_required = True
    use_curl_cffi = True
    fallback_content_selector = "div[itemprop='articleBody'], article"

    # 经济板块分页
    base_url = 'https://www.abc.es/economia/pagina-{}.html'

    custom_settings = {
        'CONCURRENT_REQUESTS': 4,
        'DOWNLOAD_DELAY': 0.5,
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_TIMEOUT': 30
    }

    async def start(self):
        yield scrapy.Request(self.base_url.format(1), callback=self.parse, dont_filter=True)

    def parse(self, response):
        if self._stop_pagination:
            return

        # 1. 提取文章链接
        # 链接格式: .../transporte-20260330200020-nt.html
        article_links = response.css('h2.v-a-t a::attr(href), a.v-a-t::attr(href)').getall()

        current_page = response.meta.get('page', 1)
        has_valid_item_in_window = False

        for link in set(article_links):
            # 列表页日期拦截: 提取 URL 中的 8 位日期指纹
            date_match = re.search(r'-(\d{8})\d+-nt\.html$', link)
            if date_match:
                date_str = date_match.group(1)
                try:
                    pub_time = datetime.strptime(date_str, '%Y%m%d')
                except:
                    continue

                if not self.should_process(link, pub_time):
                    continue

                has_valid_item_in_window = True
                yield response.follow(
                    link,
                    self.parse_detail,
                    meta={'publish_time_hint': pub_time}
                )

        # 如果没抓到或者没有触发拦截，尝试更广泛的选择器 (针对首页大图)
        if not has_valid_item_in_window:
            for link in response.css('a[href*="-2026"]::attr(href)').getall():
                if '/economia/' in link:
                    has_valid_item_in_window = True
                    yield response.follow(link, self.parse_detail)

        # 翻页逻辑
        if has_valid_item_in_window:
            next_page = current_page + 1
            yield scrapy.Request(
                self.base_url.format(next_page),
                callback=self.parse,
                meta={'page': next_page}
            )

    def parse_detail(self, response):
        # 使用 auto_parse_item 自动提取
        item = self.auto_parse_item(response)

        # 原有日期兜底逻辑
        if not item.get('publish_time'):
            pub_time = response.meta.get('publish_time_hint')
            if not pub_time:
                try:
                    scripts = response.xpath('//script[@type="application/ld+json"]/text()').getall()
                    for s in scripts:
                        data = json.loads(s)
                        if isinstance(data, dict) and 'datePublished' in data:
                            pub_time = datetime.fromisoformat(data['datePublished'][:10])
                            break
                except: pass
            if pub_time:
                item['publish_time'] = pub_time

        item['author'] = response.css('span.voc-a-n::text, .v-fc__a::text').get('ABC Economía').strip()
        item['section'] = 'Economía'

        if not self.should_process(response.url, item.get('publish_time')):
            self._stop_pagination = True
            return

        yield item
