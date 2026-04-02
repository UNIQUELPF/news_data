import scrapy
from bs4 import BeautifulSoup
from datetime import datetime
from news_scraper.spiders.base_spider import BaseNewsSpider

class MexicoGobSpider(BaseNewsSpider):
    name = 'mexico_gob'
    allowed_domains = ['www.gob.mx']
    start_urls = ['https://www.gob.mx/se/archivo/prensa?idiom=es']
    
    # 继承 BaseNewsSpider，自动初始化 mexico_gob_news 表
    target_table = 'mexico_gob_news'
    
    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.5,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 2,
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        }
    }

    def start_requests(self):
        # 墨西哥政府站分页格式为 &page=N
        # 回溯至 2026-01-01 约需 30 页
        for page in range(1, 31):
            url = f"{self.start_urls[0]}&order=DESC&page={page}"
            yield scrapy.Request(url, callback=self.parse_list, meta={'page': page})

    def parse_list(self, response):
        # 获取政府新闻稿列表链接
        articles = response.css('.archive-container a::attr(href)').getall()
        if not articles:
            articles = response.css('h2 a::attr(href)').getall()

        for link in articles:
            if '/prensa/' in link:
                full_url = response.urljoin(link)
                if full_url in self.scraped_urls:
                    continue
                self.scraped_urls.add(full_url)
                yield scrapy.Request(full_url, callback=self.parse_article)

    def parse_article(self, response):
        item = {}
        item['url'] = response.url
        
        # 官方标题提取
        title = response.css('h1::text').get() or response.xpath('//meta[@property="og:title"]/@content').get()
        item['title'] = title.strip() if title else 'Official Announcement'

        # 正文提取：政府站通常在 .article-body 或特定的文本容器中
        content_html = response.css('.article-body').get() or response.css('.content-text').get()
        if content_html:
            soup = BeautifulSoup(content_html, 'html.parser')
            # 移除噪音
            for tag in soup(['script', 'style', '.social-share', '.related-links']):
                tag.decompose()
            
            # 清洗段落
            paragraphs = []
            for p in soup.find_all(['p', 'div']):
                text = p.get_text().strip()
                if len(text) > 40:
                    paragraphs.append(text)
            
            item['content'] = "\n\n".join(paragraphs)
        
        # 精准发布日期从页面文本或 meta 标签获取
        pub_time_str = response.xpath('//meta[@property="article:published_time"]/@content').get() or \
                       response.css('.article-date::text').get()
        
        if pub_time_str:
            try:
                # 处理 ISO 或特定西语日期格式
                if 'T' in pub_time_str:
                    pub_dt = datetime.fromisoformat(pub_time_str.replace('Z', '+00:00'))
                else:
                    # 尝试解析西语日期（此处采用简化处理，若无则设为今日）
                    pub_dt = datetime.now()
                pub_time = pub_dt.replace(tzinfo=None)
            except:
                pub_time = datetime.now()
        else:
            pub_time = datetime.now()

        # 日期过滤逻辑 (由基类接管)
        if not self.filter_date(pub_time):
            return

        item['publish_time'] = pub_time
        item['author'] = 'Secretaría de Economía'
        item['language'] = 'es' # 西班牙语
        item['section'] = 'Prensa'

        if item.get('content') and len(item['content']) > 150:
            yield item
