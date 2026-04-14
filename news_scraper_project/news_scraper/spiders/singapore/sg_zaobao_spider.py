import scrapy
from datetime import datetime
import re
import json
from news_scraper.spiders.base_spider import BaseNewsSpider

class SgZaobaoSpider(BaseNewsSpider):
    name = 'sg_zaobao'

    country_code = 'SGP'

    country = '新加坡'
    allowed_domains = ['zaobao.com.sg']
    
    # 联合早报 API 接口
    api_url = 'https://www.zaobao.com.sg/_plat/api/v2/page-content/finance/singapore?page={}'
    start_urls = [api_url.format(1)]
    
    use_curl_cffi = True
    
    custom_settings = {
        'DOWNLOADER_MIDDLEWARES': {
            'news_scraper.middlewares.CurlCffiMiddleware': 543,
            'scrapy.downloadermiddlewares.useragent.UserAgentMiddleware': None,
        },
        'CURLL_CFFI_IMPERSONATE': 'chrome120',
        'DEFAULT_REQUEST_HEADERS': {
            'referer': 'https://www.zaobao.com.sg/finance/singapore',
            'x-requested-with': 'XMLHttpRequest'
        },
        'CONCURRENT_REQUESTS': 1,
        'DOWNLOAD_DELAY': 2
    }
    
    target_table = 'sg_zaobao_news'

    def parse(self, response):
        # 1. 直接处理 JSON 响应
        try:
            # 兼容性处理: 如果是 JSON 字符串
            data = json.loads(response.text)
            resp_node = data.get('response', {})
            articles = resp_node.get('articles', [])
            
            self.logger.info(f"API Response: Found {len(articles)} articles in JSON.")
        except Exception as e:
            self.logger.error(f"Failed to parse API JSON on {response.url}: {e}")
            return

        if not articles:
            return

        current_page = response.meta.get('page', 1)
        valid_items = 0
        
        for art in articles:
            href = art.get('href')
            ts = art.get('timestamp')
            
            if not href or not ts:
                continue
            
            # 2. 严密的时间过滤器
            pub_date = datetime.fromtimestamp(int(ts))
            if not self.filter_date(pub_date):
                continue

            valid_items += 1
            full_url = response.urljoin(href)
            # 详情页下钻
            yield response.follow(full_url, self.parse_article)

        # 3. 继续翻页 API
        if valid_items > 0 and current_page < 200:
            next_page = current_page + 1
            yield scrapy.Request(
                self.api_url.format(next_page),
                callback=self.parse,
                meta={'page': next_page},
                dont_filter=True
            )

    def parse_article(self, response):
        # 元数据扫描
        ld_json_scripts = response.css('script[type="application/ld+json"]::text').getall()
        pub_time = None
        
        for raw in ld_json_scripts:
            try:
                data_list = json.loads(raw)
                if not isinstance(data_list, list): data_list = [data_list]
                for data in data_list:
                    dp = data.get('datePublished', data.get('dateModified'))
                    if dp:
                        pub_time = datetime.fromisoformat(dp.replace('Z', '+00:00'))
                        break
                if pub_time: break
            except: continue

        if not pub_time:
            dm = re.search(r'story(\d{4})(\d{2})(\d{2})', response.url)
            if dm:
                y, m, d = dm.groups()
                pub_time = datetime(int(y), int(m), int(d))
            else:
                return

        if not self.filter_date(pub_time):
            return

        title = response.css('h1::text, h1 span::text').get('').strip()
        # 针对早报详情页的复合正文采集器
        content_parts = response.css('article p::text, div.article-content p::text, .post-content p::text, .article-content-container p::text').getall()
        cleaned_content = "\n\n".join([p.strip() for p in content_parts if len(p.strip()) > 10])

        if not cleaned_content:
            return

        item = {
            'url': response.url,
            'title': title,
            'content': cleaned_content,
            'publish_time': pub_time,
            'author': 'Lianhe Zaobao API',
            'language': 'zh',
            'section': 'Finance/Singapore'
        }
        
        yield item
