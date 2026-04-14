import scrapy
from bs4 import BeautifulSoup
from datetime import datetime
from news_scraper.spiders.base_spider import BaseNewsSpider

class MexicoInfobaeSpider(BaseNewsSpider):
    name = 'mexico_infobae'

    country_code = 'MEX'

    country = '墨西哥'
    allowed_domains = ['infobae.com']
    start_urls = ['https://www.infobae.com/mexico/ultimas-noticias/']
    
    # 继承 BaseNewsSpider，自动初始化 mexico_infobae_news 表
    target_table = 'mexico_infobae_news'
    
    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 0.8,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 8,
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        }
    }

    def start_requests(self):
        # Infobae 墨西哥站新闻量极大，回溯至 2026-01-01 需要约 150-200 页
        for page in range(1, 200):
            url = f"{self.start_urls[0]}?page={page}"
            yield scrapy.Request(url, callback=self.parse_list, meta={'page': page})

    def parse_list(self, response):
        # 获取 Infobae 列表页的文章链接 (feed-list-card)
        articles = response.css('a.feed-list-card::attr(href)').getall()
        if not articles:
            articles = response.css('.nd-feed-list-card a::attr(href)').getall()

        for link in articles:
            # 补齐绝对路径
            full_url = response.urljoin(link)
            if '/mexico/202' in full_url:
                if full_url in self.scraped_urls:
                    continue
                self.scraped_urls.add(full_url)
                yield scrapy.Request(full_url, callback=self.parse_article)

    def parse_article(self, response):
        item = {}
        item['url'] = response.url
        
        # 标题提取
        title = response.css('h1::text').get() or response.css('.headline::text').get()
        item['title'] = title.strip() if title else 'Unknown'

        # 正文提取：Infobae 的正文散落在多个 .paragraph 中
        content_html = response.css('.article-body').get() or response.css('.body-content').get()
        if content_html:
            soup = BeautifulSoup(content_html, 'html.parser')
            # 移除噪音
            for tag in soup(['script', 'style', 'div.ads-container', 'aside', 'figure']):
                tag.decompose()
            
            # 提取所有段落文字
            paragraphs = soup.find_all(class_='paragraph')
            if not paragraphs:
                paragraphs = soup.find_all('p')
            
            item['content'] = "\n\n".join([p.get_text().strip() for p in paragraphs if len(p.get_text()) > 30])
        
        # 精准发布日期从 meta 或 script 中获取
        pub_time_str = response.xpath('//meta[@property="article:published_time"]/@content').get()
        
        if pub_time_str:
            try:
                # 兼容 ISO 格式
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
        item['author'] = response.css('.author-name::text').get() or 'Infobae Mexico'
        item['language'] = 'es' # 西班牙语
        item['section'] = 'Ultimas Noticias'

        if item.get('content') and len(item['content']) > 200:
            yield item
