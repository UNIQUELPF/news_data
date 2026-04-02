import scrapy
from bs4 import BeautifulSoup
from datetime import datetime
from news_scraper.spiders.base_spider import BaseNewsSpider

class PortugalPublicoSpider(BaseNewsSpider):
    name = 'pt_publico'
    allowed_domains = ['publico.pt']
    start_urls = ['https://www.publico.pt/economia']
    
    # 继承 BaseNewsSpider，自动初始化 pt_publico_news 表
    target_table = 'pt_publico_news'
    
    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.2,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 4,
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        }
    }

    def start_requests(self):
        # Público 翻页格式为 ?page=N
        # 回溯至 2026-01-01 约需 150-200 页
        for page in range(1, 201):
            url = f"{self.start_urls[0]}?page={page}"
            yield scrapy.Request(url, callback=self.parse_list, meta={'page': page})

    def parse_list(self, response):
        # 获取经济版块列表中的文章链接
        # 查找带有 /economia/noticia/ 的链接
        articles = response.css('h2.headline a::attr(href)').getall() or \
                   response.css('h4.headline a::attr(href)').getall() or \
                   response.xpath('//a[contains(@href, "/noticia/")]/@href').getall()

        for link in articles:
            # 去除冗余的 ref 参数
            base_link = link.split('?')[0]
            full_url = response.urljoin(base_link)
            
            # 过滤掉非经济类或年份过旧的
            if '/202' in full_url:
                if full_url in self.scraped_urls:
                    continue
                self.scraped_urls.add(full_url)
                yield scrapy.Request(full_url, callback=self.parse_article)

    def parse_article(self, response):
        item = {}
        item['url'] = response.url
        
        # 标题提取 (H1)
        title = response.css('h1.story__title::text').get() or \
                response.css('.story__header h1::text').get() or \
                response.xpath('//meta[@property="og:title"]/@content').get()
        item['title'] = title.strip() if title else 'Notícia Público'

        # 正文提取：定位 story__body 或 story__content
        content_html = response.css('.story__body').get() or response.css('.story-body').get()
        if content_html:
            soup = BeautifulSoup(content_html, 'html.parser')
            # 移除杂质：广告、相关链接、脚本
            for tag in soup(['script', 'style', '.story__related', '.story__footer', '.ad-slot']):
                tag.decompose()
            
            # 提取所有段落
            paragraphs = []
            for p in soup.find_all('p'):
                text = p.get_text().strip()
                # 过滤掉过短或固定的非正文内容
                if len(text) > 40:
                    paragraphs.append(text)
            
            item['content'] = "\n\n".join(paragraphs)
        
        # 精准发布时间获取 (ISO 格式)
        pub_time_str = response.xpath('//meta[@property="article:published_time"]/@content').get() or \
                       response.css('time::attr(datetime)').get()
        
        if pub_time_str:
            try:
                # Público 时间格式通常带有偏移量
                pub_dt = datetime.fromisoformat(pub_time_str.replace('Z', '+00:00'))
                pub_time = pub_dt.replace(tzinfo=None)
            except:
                pub_time = datetime.now()
        else:
            pub_time = datetime.now()

        # 日期过滤逻辑 (基类接管)
        if not self.filter_date(pub_time):
            return

        item['publish_time'] = pub_time
        item['author'] = response.css('.story__author::text').get() or 'Público Portugal'
        item['language'] = 'pt' # 葡萄牙语
        item['section'] = 'Economia'

        if item.get('content') and len(item['content']) > 200:
            yield item
