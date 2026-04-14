import scrapy
from bs4 import BeautifulSoup
from datetime import datetime
from news_scraper.spiders.base_spider import BaseNewsSpider

class MexicoElFinancieroSpider(BaseNewsSpider):
    name = 'mexico_elfinanciero'

    country_code = 'MEX'

    country = '墨西哥'
    allowed_domains = ['elfinanciero.com.mx']
    start_urls = ['https://www.elfinanciero.com.mx/economia/']
    
    # 继承 BaseNewsSpider，自动初始化 mexico_elfinanciero_news 表
    target_table = 'mexico_elfinanciero_news'
    
    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.0,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 4,
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        }
    }

    def start_requests(self):
        # 翻页回溯逻辑：从第 1 页到第 80 页 (回溯至 2026 年初)
        for page in range(1, 80):
            url = self.start_urls[0] if page == 1 else f"{self.start_urls[0]}page/{page}/"
            yield scrapy.Request(url, callback=self.parse_list, meta={'page': page})

    def parse_list(self, response):
        # 获取经济板块的文章列表链接
        articles = response.css('.b-results-list a.c-link::attr(href)').getall()
        # 兼容性选择器
        if not articles:
            articles = response.css('a.c-link::attr(href)').getall()

        for link in articles:
            # 确保链接是文章链接且包含年份/月份
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

        # 正文提取：定位墨西哥金融报的正文段落 (c-paragraph)
        content_html = response.css('.c-content-body').get() or response.css('.article-body').get()
        if content_html:
            soup = BeautifulSoup(content_html, 'html.parser')
            # 剔除噪音 (广告占位符、嵌入视频)
            for tag in soup(['script', 'style', 'div.ad-container', 'aside']):
                tag.decompose()
            
            # 清洗段落：c-paragraph 是其核心标签
            paragraphs = soup.find_all('p', class_='c-paragraph')
            if not paragraphs:
                paragraphs = soup.find_all('p')
            
            item['content'] = "\n\n".join([p.get_text().strip() for p in paragraphs if len(p.get_text()) > 40])
        
        # 关键：获取发布日期 (c-date)
        pub_time_str = response.css('time.c-date::attr(dateTime)').get() or \
                       response.xpath('//meta[@property="article:published_time"]/@content').get()
        
        if pub_time_str:
            try:
                # 兼容 ISO 格式 (e.g., 2026-03-24T10:00:00.000Z)
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
        item['author'] = response.css('.c-attribution a::text').get() or 'El Financiero'
        item['language'] = 'es' # 西班牙语
        item['section'] = 'Economía'

        if item.get('content') and len(item['content']) > 200:
            yield item
