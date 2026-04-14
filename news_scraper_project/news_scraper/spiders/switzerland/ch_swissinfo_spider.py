import scrapy
from datetime import datetime
import json
from urllib.parse import urljoin, urlparse, urlunparse
from news_scraper.spiders.base_spider import BaseNewsSpider

def should_abort_request(request):
    # 拦截图片、样式、媒体和字体，只保留文档和核心脚本
    if request.resource_type in ["image", "media", "font", "stylesheet"]:
        return True
    return False

class SwissinfoSpider(BaseNewsSpider):
    name = 'ch_swissinfo'

    country_code = 'CHE'

    country = '瑞士'
    allowed_domains = ['swissinfo.ch', 'www.swissinfo.ch']
    
    target_table = 'ch_swissinfo_news'
    use_curl_cffi = False 

    def start_requests(self):
        url = 'https://www.swissinfo.ch/eng/latest-news/'
        # 列表页开启 Playwright + 拦截
        yield scrapy.Request(
            url, 
            callback=self.parse,
            meta={
                'playwright': True,
                'playwright_include_body': True,
                'playwright_page_init_callback': lambda page, request: page.route("**/*", lambda route: route.abort() if route.request.resource_type in ["image", "media", "font", "stylesheet"] else route.continue_()),
                'playwright_page_goto_params': {"wait_until": "domcontentloaded", "timeout": 60000}
            }
        )

    def parse(self, response):
        self.logger.info(f"Analyzing Swissinfo list: {response.url}")
        
        # 提取最新文章项
        articles = response.css('article.teaser-wide-card')
        if not articles:
            articles = response.css('article')
            
        self.logger.info(f"Found {len(articles)} potential articles in list.")
            
        found_ancient = False
        for art in articles:
            link = art.css('a.teaser-wide-card__link::attr(href)').get() or art.css('h3 a::attr(href)').get()
            if not link:
                continue

            # 日期探测
            list_date_str = art.css('time::attr(datetime)').get()
            if list_date_str:
                try:
                    dt_str = list_date_str.replace('Z', '+00:00')
                    list_date = datetime.fromisoformat(dt_str)
                    if not self.filter_date(list_date):
                        found_ancient = True
                        break 
                except:
                    pass

            full_url = response.urljoin(link)
            # 详情页：启用 Playwright + 拦截
            yield scrapy.Request(
                full_url, 
                callback=self.parse_article,
                meta={
                    'playwright': True,
                    'playwright_include_body': True,
                    'playwright_page_init_callback': lambda page, request: page.route("**/*", lambda route: route.abort() if route.request.resource_type in ["image", "media", "font", "stylesheet"] else route.continue_()),
                    'playwright_page_goto_params': {"wait_until": "domcontentloaded", "timeout": 60000}
                },
                dont_filter=True
            )

        if found_ancient:
            return

        # 分页
        current_offset = getattr(self, 'offset', 0) + 10
        self.offset = current_offset
        if current_offset <= 1000:
            next_url = f"https://www.swissinfo.ch/eng/latest-news/?offset={current_offset}"
            yield scrapy.Request(
                next_url, 
                callback=self.parse,
                meta={
                    'playwright': True,
                    'playwright_include_body': True,
                    'playwright_page_init_callback': lambda page, request: page.route("**/*", lambda route: route.abort() if route.request.resource_type in ["image", "media", "font", "stylesheet"] else route.continue_()),
                    'playwright_page_goto_params': {"wait_until": "domcontentloaded", "timeout": 60000}
                }
            )

    def parse_article(self, response):
        title = response.css('h1::text').get('').strip()
        lead = response.css('.lead-text__content::text').get('').strip()
        paragraphs = response.css('.article-main p::text').getall()
        body_text = '\n\n'.join([p.strip() for p in paragraphs if p.strip()])
        
        content = (lead + "\n\n" + body_text).strip()
        if not content:
             # 回退选择器
             content = (response.css('.article-main').get('')).strip()
        
        pub_time_str = response.css('time::attr(datetime)').get()
        try:
            pub_time = datetime.fromisoformat(pub_time_str.replace('Z', '+00:00'))
        except:
            pub_time = datetime.now()

        item = {
            'url': response.url,
            'title': title,
            'content': content,
            'publish_time': pub_time,
            'author': response.css('.author::text').get('swissinfo.ch').strip(),
            'language': 'en',
            'section': 'Latest News'
        }

        if len(content) > 5 or title:
            yield item
