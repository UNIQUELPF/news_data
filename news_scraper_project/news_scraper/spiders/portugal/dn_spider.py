import scrapy
from bs4 import BeautifulSoup
from datetime import datetime
from news_scraper.spiders.base_spider import BaseNewsSpider

class PortugalDNSpider(BaseNewsSpider):
    name = 'pt_dn'
    allowed_domains = ['dn.pt', 'dinheirovivo.pt']
    start_urls = ['https://www.dn.pt/economia']
    
    # 继承 BaseNewsSpider，自动初始化 pt_dn_news 表
    target_table = 'pt_dn_news'
    
    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.0,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 4,
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        }
    }

    def start_requests(self):
        # Diário de Notícias 和 Dinheiro Vivo 分页格式通常支持 ?page=N 或 /page/N/
        # 回溯至 2026-01-01 约为 180 页深度
        for page in range(1, 181):
            url = f"{self.start_urls[0]}/page/{page}/" if page > 1 else self.start_urls[0]
            yield scrapy.Request(url, callback=self.parse_list, meta={'page': page})

    def parse_list(self, response):
        # 获取经济频道和专题中的文章链接
        # 该报内容可能来自 dinheirovivo.pt 或 dn.pt
        articles = response.css('h2.headline a::attr(href)').getall() or \
                   response.css('.article-item h2 a::attr(href)').getall() or \
                   response.xpath('//a[contains(@href, "/economia/")]/@href').getall()

        for link in articles:
            # 去除可能携带的一长串追踪参数
            base_link = link.split('?')[0]
            full_url = response.urljoin(base_link)
            
            # 过滤掉非文章页面
            if '/economia/' in full_url:
                if full_url in self.scraped_urls:
                    continue
                self.scraped_urls.add(full_url)
                yield scrapy.Request(full_url, callback=self.parse_article)

    def parse_article(self, response):
        item = {}
        item['url'] = response.url
        
        # 标题提取 (H1)
        title = response.css('h1::text').get() or \
                response.css('.article-content h1::text').get() or \
                response.xpath('//meta[@property="og:title"]/@content').get()
        item['title'] = title.strip() if title else 'Notícia DN Portugal'

        # 正文提取：DN 和 Dinheiro Vivo 的容器可能不同
        content_html = response.css('.article-body').get() or \
                       response.css('.article-content-wrapper').get() or \
                       response.css('div[class*="content"]').get()
        if content_html:
            soup = BeautifulSoup(content_html, 'html.parser')
            # 移除噪音：社交块、广告、相关链接
            for tag in soup(['script', 'style', '.social-share', '.related-articles', '.ad-slot']):
                tag.decompose()
            
            # 提取所有段落
            paragraphs = []
            for p in soup.find_all(['p', 'div']):
                text = p.get_text().strip()
                # 过滤冗余信息（如 "Leia também" 等）
                if len(text) > 40 and not text.lower().startswith(('leia também', 'veja mais')):
                    paragraphs.append(text)
            
            # 保持顺序去重
            seen = set()
            unique_paragraphs = [x for x in paragraphs if not (x in seen or seen.add(x))]
            item['content'] = "\n\n".join(unique_paragraphs)
        
        # 精准发布时间获取 (ISO 格式)
        pub_time_str = response.xpath('//meta[@property="article:published_time"]/@content').get() or \
                       response.css('time::attr(datetime)').get()
        
        if pub_time_str:
            try:
                # 转换带时区的时间
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
        item['author'] = response.css('.article-author::text').get() or 'Global Media Group'
        item['language'] = 'pt' # 葡萄牙语
        item['section'] = 'Economia'

        if item.get('content') and len(item['content']) > 200:
            yield item
