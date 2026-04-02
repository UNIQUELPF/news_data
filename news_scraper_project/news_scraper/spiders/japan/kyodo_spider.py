import scrapy
from bs4 import BeautifulSoup
from datetime import datetime
from news_scraper.spiders.base_spider import BaseNewsSpider

class KyodoSpider(BaseNewsSpider):
    name = 'jp_kyodo'
    allowed_domains = ['kyodo.co.jp']
    start_urls = ['https://www.kyodo.co.jp/news/']
    
    # 继承 BaseNewsSpider，自动初始化 jp_kyodo_news 表
    target_table = 'jp_kyodo_news'
    
    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.0,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 4,
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
            'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
        }
    }

    def start_requests(self):
        # 共同社新闻列表，回溯 50 页左右
        for page in range(1, 51):
            url = self.start_urls[0] if page == 1 else f"{self.start_urls[0]}page/{page}/"
            yield scrapy.Request(url, callback=self.parse_list, meta={'page': page})

    def parse_list(self, response):
        # 获取新闻列表链接 (修正选择器：a 标签本身拥有该类)
        articles = response.css('a.main_archive__content--ttl::attr(href)').getall()
        
        for link in articles:
            full_url = response.urljoin(link)
            if full_url in self.scraped_urls:
                continue
            self.scraped_urls.add(full_url)
            yield scrapy.Request(full_url, callback=self.parse_article)

    def parse_article(self, response):
        item = {}
        item['url'] = response.url
        
        # 1. 标题提取
        title = response.css('section.post_ttl h1::text').get() or \
                response.css('h1.main_ttl::text').get() or \
                response.xpath('//meta[@property="og:title"]/@content').get()
        item['title'] = title.strip() if title else ''

        # 2. 正文提取
        content_html = response.css('section.post_container').get() or \
                       response.css('.entry-content').get() or \
                       response.css('article').get()
        
        if content_html:
            soup = BeautifulSoup(content_html, 'html.parser')
            # 移除脚本和不相关的 UI
            for tag in soup(['script', 'style', 'nav', 'aside', '.sns_btn', '.post_ttl', '.post_detail']):
                tag.decompose()
            
            # 提取段落文本
            paragraphs = [p.get_text().strip() for p in soup.find_all(['p', 'div']) if len(p.get_text().strip()) > 30]
            # 去重并合并
            seen = set()
            unique_paragraphs = [x for x in paragraphs if not (x in seen or seen.add(x))]
            item['content'] = "\n\n".join(unique_paragraphs)
        
        # 3. 发布时间提取
        # <time class="post_detail__date">2026.03.27 17:20</time>
        pub_time_str = response.css('time.post_detail__date::text').get() or \
                       response.css('.main_date::text').get() or \
                       response.xpath('//meta[@property="article:published_time"]/@content').get()
        
        if pub_time_str:
            try:
                # 兼容 "2026.03.11 09:56" 或 ISO
                from dateutil import parser
                pub_dt = parser.parse(pub_time_str.replace('.', '-'))
                pub_time = pub_dt.replace(tzinfo=None)
            except:
                pub_time = datetime.now()
        else:
            pub_time = datetime.now()

        # 4. 日期过滤核心逻辑 (2026-01-01 后)
        if not self.filter_date(pub_time):
            return

        item['publish_time'] = pub_time
        item['author'] = 'Kyodo News Japan'
        item['language'] = 'ja'
        item['section'] = response.url.split('/')[3] if len(response.url.split('/')) > 3 else 'news'

        if item.get('content') and len(item['content']) > 100:
            yield item
