import scrapy
from datetime import datetime
import json
from news_scraper.spiders.base_spider import BaseNewsSpider

class SgBusinessTimesSpider(BaseNewsSpider):
    name = 'sg_businesstimes'

    country_code = 'SGP'

    country = '新加坡'
    allowed_domains = ['businesstimes.com.sg']
    
    # 商业时报隐藏的分页 API (v1)
    api_url = 'https://www.businesstimes.com.sg/_plat/api/v1/articles/sections?size=20&sections=singapore_economy-policy&page={}'
    start_urls = [api_url.format(1)]
    
    use_curl_cffi = True
    
    custom_settings = {
        'DOWNLOADER_MIDDLEWARES': {
            'news_scraper.middlewares.CurlCffiMiddleware': 543,
            'scrapy.downloadermiddlewares.useragent.UserAgentMiddleware': None,
        },
        'CURLL_CFFI_IMPERSONATE': 'chrome120',
        'DEFAULT_REQUEST_HEADERS': {
            'referer': 'https://www.businesstimes.com.sg/singapore/economy-policy',
            'x-requested-with': 'XMLHttpRequest'
        },
        'CONCURRENT_REQUESTS': 1,
        'DOWNLOAD_DELAY': 2
    }
    
    target_table = 'sg_businesstimes_news'

    def parse(self, response):
        try:
            data = json.loads(response.text)
            items = data.get('data', {}).get('items', [])
            self.logger.info(f"API (v1) Response: Found {len(items)} items on page {response.meta.get('page', 1)}")
        except Exception as e:
            self.logger.error(f"Failed to parse API JSON on {response.url}: {e}")
            return

        if not items:
            self.logger.info("No more items found in API response.")
            return

        current_page = response.meta.get('page', 1)
        valid_items = 0
        
        for item in items:
            article_data = item.get('articleData', {})
            href = article_data.get('urlPath')
            # 使用 ISO 格式的 publishTime: 2026-03-20T02:30:00.000Z
            pub_time_raw = article_data.get('publishTime')
            
            if not href or not pub_time_raw:
                continue
            
            try:
                pub_date = datetime.fromisoformat(pub_time_raw.replace('Z', '+00:00'))
            except:
                continue

            # 列表级日期拦截
            if not self.filter_date(pub_date):
                continue

            valid_items += 1
            yield response.follow(
                href, 
                self.parse_article,
                meta={'pub_date': pub_date}
            )

        # 翻页推进
        if valid_items > 0 and current_page < 1000:
            next_page = current_page + 1
            yield scrapy.Request(
                self.api_url.format(next_page),
                callback=self.parse,
                meta={'page': next_page},
                dont_filter=True
            )

    def parse_article(self, response):
        pub_time = response.meta.get('pub_date')

        # 1. 标题提取
        title = response.css('h1::text, h1 span::text').get('').strip()
        
        # 2. 正文内容
        #  commercial times typically uses font-lucida for body
        content_parts = response.css('div.font-lucida p::text, div.mx-auto.font-lucida p::text, div.article-content p::text').getall()
        # 清除过短或重复干扰
        cleaned_content = "\n\n".join([p.strip() for p in content_parts if len(p.strip()) > 15])

        if not cleaned_content:
            # 兼容性兜底
            cleaned_content = "\n\n".join(response.css('main p::text').getall())

        if not cleaned_content:
            return

        item = {
            'url': response.url,
            'title': title,
            'content': cleaned_content,
            'publish_time': pub_time,
            'author': 'Business Times SG',
            'language': 'en',
            'section': 'Economy & Policy'
        }
        
        yield item
