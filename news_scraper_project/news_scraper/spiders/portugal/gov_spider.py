import scrapy
from bs4 import BeautifulSoup
from datetime import datetime
from news_scraper.spiders.base_spider import BaseNewsSpider

class PortugalGovSpider(BaseNewsSpider):
    name = 'pt_gov'
    allowed_domains = ['portugal.gov.pt']
    start_urls = ['https://www.portugal.gov.pt/pt/gc25/comunicacao/noticias']
    
    # 继承 BaseNewsSpider，自动初始化 pt_gov_news 表
    target_table = 'pt_gov_news'
    
    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.5,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 2,
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        }
    }

    def start_requests(self):
        # 葡萄牙政府站翻页通常支持 p 参数
        # 深度扫描 75 页即可回溯至 2026-01-01 之前
        for page in range(1, 76):
            url = f"{self.start_urls[0]}?p={page}"
            yield scrapy.Request(url, callback=self.parse_list, meta={'page': page})

    def parse_list(self, response):
        self.logger.info(f"Received response from {response.url} with length {len(response.text)}")
        # 更加宽松的链接提取逻辑
        articles = response.xpath('//a[contains(@href, "/noticia?")]/@href').getall()
        self.logger.info(f"Discovered {len(articles)} potential articles on {response.url}")

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
        item['title'] = title.strip() if title else 'Official Gov Announcement'
        self.logger.info(f"Parsing article: {item['title']} at {response.url}")

        # 正文提取：div#regText.gov-texts 是核心容器
        content_html = response.css('div#regText.gov-texts').get() or response.css('.noticia-corpo').get()
        if content_html:
            soup = BeautifulSoup(content_html, 'html.parser')
            for tag in soup(['script', 'style', 'nav', '.noticia-galeria']):
                tag.decompose()
            
            paragraphs = []
            for p in soup.find_all(['p', 'div', 'li']):
                text = p.get_text().strip()
                if len(text) > 30 and not text.startswith(('Partilhar', 'Voltar')):
                    paragraphs.append(text)
            
            seen = set()
            item['content'] = "\n\n".join([x for x in paragraphs if not (x in seen or seen.add(x))])
        
        # 发布时间获取
        pub_time_raw = response.css('div.time::text').get()
        if pub_time_raw:
            self.logger.info(f"Found date raw: {pub_time_raw}")
            try:
                clean_date = pub_time_raw.replace('às', '').replace('h', ':').strip()
                from dateutil import parser
                pub_time = parser.parse(clean_date)
            except Exception as e:
                self.logger.warning(f"Date parse failed for {pub_time_raw}: {e}")
                pub_time = datetime.now()
        else:
            pub_time = datetime.now()

        if not self.filter_date(pub_time):
            self.logger.info(f"Article filtered out due to date: {pub_time} vs {self.cutoff_date}")
            return

        item['publish_time'] = pub_time
        item['author'] = 'Governo da República Portuguesa'
        item['language'] = 'pt'
        item['section'] = 'Comunicado Oficial'

        if item.get('content') and len(item['content']) > 50:
            self.logger.info(f"Scraped article: {item['title']} - {item['url']}")
            yield item
