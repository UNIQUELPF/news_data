import scrapy
from bs4 import BeautifulSoup
from datetime import datetime
from news_scraper.spiders.base_spider import BaseNewsSpider

class PortugalTekSapoSpider(BaseNewsSpider):
    name = 'pt_tek_sapo'
    allowed_domains = ['tek.sapo.pt']
    start_urls = ['https://tek.sapo.pt/ultimas/']
    
    # 继承 BaseNewsSpider，自动初始化 pt_tek_sapo_news 表
    target_table = 'pt_tek_sapo_news'
    
    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.0,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 4,
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        }
    }

    def start_requests(self):
        # SAPO Tek 使用标准 WordPress 分页格式 /page/N/
        # 该站科技新闻产出极快，回溯至 2026-01-01 约为 180-250 页
        for page in range(1, 251):
            url = self.start_urls[0] if page == 1 else f"{self.start_urls[0]}page/{page}/"
            yield scrapy.Request(url, callback=self.parse_list, meta={'page': page})

    def parse_list(self, response):
        # 列表中的链接格式通常为 /noticias/.../artigos/...
        articles = response.xpath('//a[contains(@href, "/artigos/")]/@href').getall()

        for link in articles:
            full_url = response.urljoin(link)
            if full_url in self.scraped_urls:
                continue
            self.scraped_urls.add(full_url)
            yield scrapy.Request(full_url, callback=self.parse_article)

    def parse_article(self, response):
        item = {}
        item['url'] = response.url
        
        # 标题提取 (H1 或 og:title)
        title = response.css('h1::text').get() or response.xpath('//meta[@property="og:title"]/@content').get()
        item['title'] = title.strip() if title else 'SAPO Tek Report'

        # 正文提取：定位 article-content 或 post-content
        content_html = response.css('.article-content').get() or \
                       response.css('.post-content').get() or \
                       response.css('div[class*="content"]').get()
        if content_html:
            soup = BeautifulSoup(content_html, 'html.parser')
            # 移除杂质
            for tag in soup(['script', 'style', '.related-posts', '.social-share']):
                tag.decompose()
            
            # 文本分段落提取
            paragraphs = []
            for p in soup.find_all(['p', 'div']):
                text = p.get_text().strip()
                if len(text) > 40:
                    paragraphs.append(text)
            
            # 使用有序去重
            seen = set()
            unique_paragraphs = [x for x in paragraphs if not (x in seen or seen.add(x))]
            item['content'] = "\n\n".join(unique_paragraphs)
        
        # 发布时间获取 (ISO 格式)
        pub_time_str = response.xpath('//meta[@property="article:published_time"]/@content').get() or \
                       response.css('time::attr(datetime)').get()
        
        if pub_time_str:
            try:
                # 兼容 ISO 带有时区的格式
                pub_dt = datetime.fromisoformat(pub_time_str.replace('Z', '+00:00'))
                pub_time = pub_dt.replace(tzinfo=None)
            except:
                pub_time = datetime.now()
        else:
            pub_time = datetime.now()

        # 日期过滤逻辑 (由 BaseNewsSpider 接管)
        if not self.filter_date(pub_time):
            return

        item['publish_time'] = pub_time
        item['author'] = response.css('.article-author::text').get() or 'SAPO TEK Desk'
        item['language'] = 'pt' # 葡萄牙语
        item['section'] = 'Tech/Digital'

        if item.get('content') and len(item['content']) > 200:
            yield item
