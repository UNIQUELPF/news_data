import scrapy
from bs4 import BeautifulSoup
from datetime import datetime
from news_scraper.spiders.base_spider import BaseNewsSpider

class MyanmarElevenSpider(BaseNewsSpider):
    name = 'mm_eleven'

    country_code = 'MMR'

    country = '缅甸'
    allowed_domains = ['news-eleven.com']
    start_urls = ['https://news-eleven.com/business']
    
    # 继承 BaseNewsSpider，自动初始化 mm_eleven_news 表
    target_table = 'mm_eleven_news'
    
    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.0,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 4,
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        }
    }

    def start_requests(self):
        # Drupal 分页格式为 ?page=0, ?page=1...
        # 从 1 月 1 日开始回溯，由于新闻量大，需要回溯至少 100 页
        for page in range(0, 100):
            url = f"{self.start_urls[0]}?page={page}"
            yield scrapy.Request(url, callback=self.parse_list, meta={'page': page})

    def parse_list(self, response):
        # 获取 Drupal 生成的文章链接 (.frontpage-title a)
        articles = response.css('.frontpage-title a::attr(href)').getall()
        if not articles:
            articles = response.css('.news-top-featured-large-category a::attr(href)').getall()

        for link in articles:
            full_url = response.urljoin(link)
            if '/article/' in full_url:
                if full_url in self.scraped_urls:
                    continue
                self.scraped_urls.add(full_url)
                yield scrapy.Request(full_url, callback=self.parse_article)

    def parse_article(self, response):
        item = {}
        item['url'] = response.url
        
        # 标题提取 (带有缅甸语字符处理)
        title = response.css('h1.article-title::text').get() or response.xpath('//meta[@property="og:title"]/@content').get()
        item['title'] = title.strip() if title else 'Unknown'

        # 正文提取：Drupal 典型正文区域
        content_html = response.css('.field-name-body').get() or response.css('.article-content').get()
        if content_html:
            soup = BeautifulSoup(content_html, 'html.parser')
            # 移除噪音
            for tag in soup(['script', 'style', 'div.adsbygoogle']):
                tag.decompose()
            
            # 提取缅甸语或英语正文
            paragraphs = []
            for p in soup.find_all('p'):
                text = p.get_text().strip()
                if len(text) > 20: # 缅甸语段落可能较短，设为 20
                    paragraphs.append(text)
            
            item['content'] = "\n\n".join(paragraphs)
        
        # 精准发布日期从 meta 标签获取
        pub_time_str = response.xpath('//meta[@property="article:published_time"]/@content').get() or \
                       response.xpath('//meta[@name="publish-date"]/@content').get()
        
        if pub_time_str:
            try:
                # 兼容多种 ISO 格式
                if 'T' in pub_time_str:
                    pub_dt = datetime.fromisoformat(pub_time_str.replace('Z', '+00:00'))
                else:
                    pub_dt = datetime.strptime(pub_time_str, '%Y-%m-%d %H:%M:%S')
                pub_time = pub_dt.replace(tzinfo=None)
            except:
                pub_time = datetime.now()
        else:
            # 尝试解析页面中文本日期
            pub_time = datetime.now()

        # 日期过滤逻辑
        if not self.filter_date(pub_time):
            return

        item['publish_time'] = pub_time
        item['author'] = 'Eleven Media Group'
        item['language'] = 'my' if any('\u1000' <= char <= '\u109f' for char in item['title']) else 'en'
        item['section'] = 'Business'

        if item.get('content') and len(item['content']) > 100:
            yield item
