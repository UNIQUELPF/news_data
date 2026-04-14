import scrapy
from bs4 import BeautifulSoup
from datetime import datetime
from news_scraper.spiders.base_spider import BaseNewsSpider

class MyanmarBizTodaySpider(BaseNewsSpider):
    name = 'mm_mmbiztoday'

    country_code = 'MMR'

    country = '缅甸'
    allowed_domains = ['mmbiztoday.com']
    start_urls = ['https://mmbiztoday.com/category/investment-and-finance/']
    
    # 继承 BaseNewsSpider，自动初始化 mm_mmbiztoday_news 表
    target_table = 'mm_mmbiztoday_news'
    
    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.0,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 4,
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        }
    }

    def start_requests(self):
        # 翻页回溯逻辑：从第 1 页到约第 30 页 (涵盖 2026 年初)
        for page in range(1, 30):
            url = self.start_urls[0] if page == 1 else f"{self.start_urls[0]}page/{page}/"
            yield scrapy.Request(url, callback=self.parse_list, meta={'page': page})

    def parse_list(self, response):
        # 获取列表页的文章链接 (td-module-title a)
        articles = response.css('.td-module-title h3 a::attr(href)').getall()
        if not articles:
            articles = response.css('h3.entry-title a::attr(href)').getall()

        for link in articles:
            if link and link.startswith('http'):
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

        # 正文提取：定位 WordPress 主要内容区
        content_html = response.css('.td-post-content').get() or response.css('.entry-content').get()
        if content_html:
            soup = BeautifulSoup(content_html, 'html.parser')
            # 剔除噪音 (广告占位符、脚本)
            for tag in soup(['script', 'style', 'div.adsbygoogle', 'aside']):
                tag.decompose()
            
            # 清洗段落
            paragraphs = soup.find_all('p')
            item['content'] = "\n\n".join([p.get_text().strip() for p in paragraphs if len(p.get_text()) > 30])
        
        # 关键：获取发布日期 (meta 或 time 标签)
        pub_time_str = response.xpath('//meta[@property="article:published_time"]/@content').get() or response.css('time.entry-date::attr(datetime)').get()
        
        if pub_time_str:
            try:
                # 兼容 ISO 格式 (e.g., 2026-03-20T10:00:00Z)
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
        item['author'] = response.css('.td-post-author-name a::text').get() or 'Myanmar Business Today'
        item['language'] = 'en'
        item['section'] = 'Investment & Finance'

        if item.get('content') and len(item['content']) > 150:
            yield item
