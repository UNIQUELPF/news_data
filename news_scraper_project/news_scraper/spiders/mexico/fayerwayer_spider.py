import scrapy
from bs4 import BeautifulSoup
from datetime import datetime
from news_scraper.spiders.base_spider import BaseNewsSpider

class MexicoFayerWayerSpider(BaseNewsSpider):
    name = 'mexico_fayerwayer'
    allowed_domains = ['fayerwayer.com']
    start_urls = ['https://www.fayerwayer.com/comercial/']
    
    # 继承 BaseNewsSpider，自动初始化 mexico_fayerwayer_news 表
    target_table = 'mexico_fayerwayer_news'
    
    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.0,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 4,
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        }
    }

    def start_requests(self):
        # Metro World News 架构分页为 /page/N/
        # 回溯至 2026-01-01 约需 60-80 页
        for page in range(1, 80):
            url = self.start_urls[0] if page == 1 else f"{self.start_urls[0]}page/{page}/"
            yield scrapy.Request(url, callback=self.parse_list, meta={'page': page})

    def parse_list(self, response):
        # 获取科技新闻列表链接 (b-results-list)
        articles = response.css('.b-results-list a.c-link::attr(href)').getall()
        if not articles:
            articles = response.css('a.c-link::attr(href)').getall()

        for link in articles:
            if '/202' in link:
                full_url = response.urljoin(link)
                if full_url in self.scraped_urls:
                    continue
                self.scraped_urls.add(full_url)
                yield scrapy.Request(full_url, callback=self.parse_article)

    def parse_article(self, response):
        item = {}
        item['url'] = response.url
        
        # 标题提取
        title = response.css('h1::text').get() or response.xpath('//meta[@property="og:title"]/@content').get()
        item['title'] = title.strip() if title else 'Unknown'

        # 正文提取：定位 FayerWayer 的正文段落
        content_html = response.css('.article-body').get() or response.css('.c-content-body').get()
        if content_html:
            soup = BeautifulSoup(content_html, 'html.parser')
            # 移除噪音
            for tag in soup(['script', 'style', 'div.ad-container', 'aside']):
                tag.decompose()
            
            # 提取所有段落 (MetroCMS 使用 c-paragraph)
            paragraphs = soup.find_all('p', class_='c-paragraph')
            if not paragraphs:
                paragraphs = soup.find_all('p')
            
            item['content'] = "\n\n".join([p.get_text().strip() for p in paragraphs if len(p.get_text()) > 40])
        
        # 精准发布日期获取
        pub_time_str = response.css('time.c-date::attr(dateTime)').get() or \
                       response.xpath('//meta[@property="article:published_time"]/@content').get()
        
        if pub_time_str:
            try:
                # 兼容多种 ISO 格式
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
        item['author'] = response.css('.c-attribution a::text').get() or 'FayerWayer Mexico'
        item['language'] = 'es' # 西班牙语
        item['section'] = 'Tech & Business'

        if item.get('content') and len(item['content']) > 200:
            yield item
