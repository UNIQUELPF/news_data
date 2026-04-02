import scrapy
from bs4 import BeautifulSoup
from datetime import datetime
from news_scraper.spiders.base_spider import BaseNewsSpider

class MyanmarIrrawaddySpider(BaseNewsSpider):
    name = 'mm_irrawaddy'
    allowed_domains = ['irrawaddy.com']
    start_urls = ['https://www.irrawaddy.com/category/news']
    
    # 继承 BaseNewsSpider，自动初始化 mm_irrawaddy_news 表
    target_table = 'mm_irrawaddy_news'
    
    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.0,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 4,
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        }
    }

    def start_requests(self):
        # Irrawaddy 分页格式通常为 /category/news/page/2/
        # 从 1 月 1 日开始回溯，大约需要 50-60 页
        for page in range(1, 60):
            url = self.start_urls[0] if page == 1 else f"{self.start_urls[0]}/page/{page}/"
            yield scrapy.Request(url, callback=self.parse_list, meta={'page': page})

    def parse_list(self, response):
        # 获取 JNews 框架下的文章链接 (jeg_post_title a)
        articles = response.css('.jeg_post_title a::attr(href)').getall()
        # 兼容其他版本
        if not articles:
            articles = response.css('h3 a::attr(href)').getall()

        for link in articles:
            if link and link.startswith('https://www.irrawaddy.com/'):
                if link in self.scraped_urls:
                    continue
                self.scraped_urls.add(link)
                yield scrapy.Request(link, callback=self.parse_article)

    def parse_article(self, response):
        item = {}
        item['url'] = response.url
        
        # 标题提取
        title = response.css('h1.entry-title::text').get() or response.xpath('//meta[@property="og:title"]/@content').get()
        item['title'] = title.strip() if title else 'Unknown'

        # 正文提取：主要是 entry-content
        content_html = response.css('.entry-content').get()
        if content_html:
            soup = BeautifulSoup(content_html, 'html.parser')
            # 剔除噪音 (分享按钮、相关推荐、广告)
            for tag in soup(['script', 'style', 'div.jeg_share_links', 'div.related-content', 'aside']):
                tag.decompose()
            
            # 清洗正文
            paragraphs = []
            for p in soup.find_all('p'):
                text = p.get_text().strip()
                if len(text) > 40 and 'The Irrawaddy' not in text:
                    paragraphs.append(text)
            
            item['content'] = "\n\n".join(paragraphs)
        
        # 精准发布日期
        pub_time_str = response.xpath('//meta[@property="article:published_time"]/@content').get() or response.css('time.entry-date::attr(datetime)').get()
        
        if pub_time_str:
            try:
                # 兼容 ISO 格式
                pub_dt = datetime.fromisoformat(pub_time_str.replace('Z', '+00:00'))
                pub_time = pub_dt.replace(tzinfo=None)
            except:
                pub_time = datetime.now()
        else:
            pub_time = datetime.now()

        # 日期过滤逻辑 (继承自基类)
        if not self.filter_date(pub_time):
            return

        item['publish_time'] = pub_time
        item['author'] = response.css('.entry-author a::text').get() or 'The Irrawaddy'
        item['language'] = 'en'
        item['section'] = 'Burma News'

        if item.get('content') and len(item['content']) > 150:
            yield item
