import scrapy
from bs4 import BeautifulSoup
from datetime import datetime
from news_scraper.spiders.base_spider import BaseNewsSpider

class NigeriaVanguardSpider(BaseNewsSpider):
    name = 'ng_vanguard'
    allowed_domains = ['vanguardngr.com']
    start_urls = ['https://www.vanguardngr.com/category/business/']
    
    # 继承 BaseNewsSpider，自动初始化 ng_vanguard_news 表
    target_table = 'ng_vanguard_news'
    
    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.5,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 4,
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        }
    }

    def start_requests(self):
        # Vanguard 使用 WordPress 标准翻页 /page/N/
        # 该报商业版发稿量极大，回溯至 2026-01-01 约需 200 页
        for page in range(1, 201):
            url = self.start_urls[0] if page == 1 else f"{self.start_urls[0]}page/{page}/"
            yield scrapy.Request(url, callback=self.parse_list, meta={'page': page})

    def parse_list(self, response):
        # 获取文章列表中的链接 (entry-header)
        articles = response.css('header.entry-header a::attr(href)').getall() or \
                   response.css('.archive-content h2 a::attr(href)').getall()

        for link in articles:
            full_url = response.urljoin(link)
            # 过滤掉非文章页面或年份过旧的页面
            if '/202' in full_url:
                if full_url in self.scraped_urls:
                    continue
                self.scraped_urls.add(full_url)
                yield scrapy.Request(full_url, callback=self.parse_article)

    def parse_article(self, response):
        item = {}
        item['url'] = response.url
        
        # 标题提取
        title = response.css('h1.entry-title::text').get() or response.xpath('//meta[@property="og:title"]/@content').get()
        item['title'] = title.strip() if title else 'Unknown'

        # 正文提取：entry-content
        content_html = response.css('.entry-content').get() or response.css('.article-content').get()
        if content_html:
            soup = BeautifulSoup(content_html, 'html.parser')
            # 移除噪音
            for tag in soup(['script', 'style', 'div.ad-container', 'aside', 'div.sharedaddy']):
                tag.decompose()
            
            # 提取段落文本
            paragraphs = []
            for p in soup.find_all('p'):
                text = p.get_text().strip()
                if len(text) > 40:
                    paragraphs.append(text)
            
            item['content'] = "\n\n".join(paragraphs)
        
        # 发布时间（尼日利亚 GMT+1）
        pub_time_str = response.xpath('//meta[@property="article:published_time"]/@content').get() or \
                       response.css('div.entry-date::text').get() or \
                       response.css('time::attr(datetime)').get()
        
        if pub_time_str:
            try:
                # 兼容 ISO or text 格式 "March 19, 2026"
                if 'T' in pub_time_str:
                    pub_dt = datetime.fromisoformat(pub_time_str.replace('Z', '+00:00'))
                else:
                    # 尝试解析文本日期
                    from dateutil import parser
                    pub_dt = parser.parse(pub_time_str)
                pub_time = pub_dt.replace(tzinfo=None)
            except:
                pub_dt = datetime.now()
                pub_time = pub_dt.replace(tzinfo=None)
        else:
            pub_time = datetime.now()

        # 日期过滤逻辑 (基类接管)
        if not self.filter_date(pub_time):
            return

        item['publish_time'] = pub_time
        item['author'] = response.css('.entry-author-name::text').get() or 'Vanguard News'
        item['language'] = 'en' # 尼日利亚英语
        item['section'] = 'Business'

        if item.get('content') and len(item['content']) > 200:
            yield item
