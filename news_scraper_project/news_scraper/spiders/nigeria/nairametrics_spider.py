import scrapy
from bs4 import BeautifulSoup
from datetime import datetime
from news_scraper.spiders.base_spider import BaseNewsSpider

class NigeriaNairametricsSpider(BaseNewsSpider):
    name = 'ng_nairametrics'
    allowed_domains = ['nairametrics.com']
    start_urls = ['https://nairametrics.com/category/economy/']
    
    # 继承 BaseNewsSpider，自动初始化 ng_nairametrics_news 表
    target_table = 'ng_nairametrics_news'
    
    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.0,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 4,
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        }
    }

    def start_requests(self):
        # JNews 分页格式为 /page/N/
        # 回溯至 2026-01-01 约为 120 页
        for page in range(1, 121):
            url = self.start_urls[0] if page == 1 else f"{self.start_urls[0]}page/{page}/"
            yield scrapy.Request(url, callback=self.parse_list, meta={'page': page})

    def parse_list(self, response):
        # 获取 JNews 列表页文章链接
        articles = response.css('h3.jeg_post_title a::attr(href)').getall()
        if not articles:
            articles = response.css('.jeg_main_content a::attr(href)').getall()

        for link in articles:
            full_url = response.urljoin(link)
            # 过滤掉非文章页面
            if '/202' in full_url:
                if full_url in self.scraped_urls:
                    continue
                self.scraped_urls.add(full_url)
                yield scrapy.Request(full_url, callback=self.parse_article)

    def parse_article(self, response):
        item = {}
        item['url'] = response.url
        
        # 标题提取
        title = response.css('h1.jeg_ad_article_title::text').get() or \
                response.css('.entry-header h1::text').get() or \
                response.xpath('//meta[@property="og:title"]/@content').get()
        item['title'] = title.strip() if title else 'Nairametrics Analysis'

        # 正文提取：content-inner
        content_html = response.css('.content-inner').get() or response.css('.entry-content').get()
        if content_html:
            soup = BeautifulSoup(content_html, 'html.parser')
            # 移除噪音
            for tag in soup(['script', 'style', '.jeg_ad', '.entry-pagination', '.jeg_post_tags']):
                tag.decompose()
            
            # 清洗正文段落
            paragraphs = []
            for p in soup.find_all('p'):
                text = p.get_text().strip()
                if len(text) > 40:
                    paragraphs.append(text)
            
            item['content'] = "\n\n".join(paragraphs)
        
        # 发布时间（尼日利亚 GMT+1）
        pub_time_str = response.xpath('//meta[@property="article:published_time"]/@content').get() or \
                       response.css('time::attr(datetime)').get()
        
        if pub_time_str:
            try:
                # 兼容多种格式
                pub_dt = datetime.fromisoformat(pub_time_str.replace('Z', '+00:00'))
                pub_time = pub_dt.replace(tzinfo=None)
            except:
                pub_time = datetime.now()
        else:
            pub_time = datetime.now()

        # 日期过滤逻辑
        if not self.filter_date(pub_time):
            return

        item['publish_time'] = pub_time
        item['author'] = response.css('.jeg_meta_author a::text').get() or 'Nairametrics Desk'
        item['language'] = 'en' # 英语
        item['section'] = 'Economy'

        if item.get('content') and len(item['content']) > 200:
            yield item
