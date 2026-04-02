import scrapy
from bs4 import BeautifulSoup
from datetime import datetime
from news_scraper.spiders.base_spider import BaseNewsSpider

class PortugalCMSpider(BaseNewsSpider):
    name = 'pt_cm'
    allowed_domains = ['cmjornal.pt']
    start_urls = ['https://www.cmjornal.pt/economia']
    
    # 继承 BaseNewsSpider，自动初始化 pt_cm_news 表
    target_table = 'pt_cm_news'
    
    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.0,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 4,
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        }
    }

    def start_requests(self):
        # 初始抓取第一页
        yield scrapy.Request(self.start_urls[0], callback=self.parse_list)
        
        # 模拟 AJAX 翻页逻辑：步长 12
        # 回溯至 2026-01-01 约需 200-300 次迭代
        base_ajax = "https://www.cmjornal.pt/economia/loadmore?friendlyUrl=economia&contentStartIndex="
        for index in range(12, 3600, 12):
            url = f"{base_ajax}{index}"
            yield scrapy.Request(url, callback=self.parse_list, meta={'index': index})

    def parse_list(self, response):
        # CM 的链接格式通常为 /economia/detalhe/...
        articles = response.xpath('//a[contains(@href, "/detalhe/")]/@href').getall()

        for link in articles:
            full_url = response.urljoin(link)
            if full_url in self.scraped_urls:
                continue
            self.scraped_urls.add(full_url)
            yield scrapy.Request(full_url, callback=self.parse_article)

    def parse_article(self, response):
        item = {}
        item['url'] = response.url
        
        # 标题提取 (H1)
        title = response.css('h1::text').get() or response.xpath('//meta[@property="og:title"]/@content').get()
        item['title'] = title.strip() if title else 'Correio da Manhã Business'

        # 正文提取：容器为 .texto_noticia 或 .detalhe_corpo
        content_html = response.css('.texto_noticia').get() or response.css('.detalhe_corpo').get()
        if content_html:
            soup = BeautifulSoup(content_html, 'html.parser')
            # 移除杂质
            for tag in soup(['script', 'style', '.relacionadas', '.tags', '.publicidade']):
                tag.decompose()
            
            # 提取所有段落
            paragraphs = []
            for p in soup.find_all(['p', 'div']):
                text = p.get_text().strip()
                if len(text) > 40:
                    paragraphs.append(text)
            
            item['content'] = "\n\n".join(paragraphs)
        
        # 发布时间获取
        pub_time_str = response.xpath('//meta[@property="article:published_time"]/@content').get() or \
                       response.css('time::attr(datetime)').get()
        
        if pub_time_str:
            try:
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
        item['author'] = 'Correio da Manhã'
        item['language'] = 'pt'
        item['section'] = 'Economia'

        if item.get('content') and len(item['content']) > 200:
            yield item
