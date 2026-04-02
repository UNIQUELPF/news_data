import scrapy
import re
from datetime import datetime
from news_scraper.spiders.base_spider import BaseNewsSpider

class BnBrudirectSpider(BaseNewsSpider):
    name = 'bn_brudirect'
    allowed_domains = ['brudirect.com']
    
    # 列表页: 其中 category=national-headline 对应新闻版块
    base_url = 'https://brudirect.com/result.php?title=&category=national-headline&subcategory=&p={}'
    start_urls = [base_url.format(1)]
    
    # 数据库表名配置 (Brunei -> bn, Site -> brudirect)
    target_table = 'bn_brudirect_news'
    
    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'CONCURRENT_REQUESTS': 4, # 鉴于站点响应慢，限制并发
        'DOWNLOAD_DELAY': 2,
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_TIMEOUT': 60, # 极力延长超时以应对超慢的外网链路
    }

    def parse(self, response):
        # 1. 提取所有 /post/ 链接
        links = response.css('a[href*="/post/"]::attr(href)').getall()
        # 补全域名 (如果是相对路径)
        links = [response.urljoin(l) for l in set(links)]
        
        current_page = response.meta.get('page', 1)
        valid_links_count = 0
        
        for link in links:
            # 格式: /post/21/02/2026-title...
            # 这种 URL 结构可以直接预过滤日期
            url_date = None
            date_match = re.search(r'/post/(\d{2})/(\d{2})/(\d{4})-', link)
            if date_match:
                d, m, y = date_match.groups()
                try:
                    url_date = datetime(year=int(y), month=int(m), day=int(d))
                except: pass
            
            # 只有符合 2026/01/01 及以后日期的链接才发起 Request
            if url_date and not self.filter_date(url_date):
                continue
            
            valid_links_count += 1
            yield response.follow(link, self.parse_article)
            
        # 2. 翻页探测 (只要当前页存在 2026 之后的文章，或者 URL 无法通过正则排除，就往后探测)
        # 文莱站历史极深（3000+页），如果不带预过滤，翻页会极其庞大
        if valid_links_count > 0 and current_page < 1000:
            next_page = current_page + 1
            yield scrapy.Request(
                self.base_url.format(next_page),
                callback=self.parse,
                meta={'page': next_page}
            )

    def parse_article(self, response):
        # 1. 提取标题 (该站点标准新闻标题在 h2)
        title = response.css('h2::text').get('').strip()
        if not title:
            # 备选 H1 或 H3
            title = response.css('h1::text, h3::text').get('').strip()
        
        # 2. 提取日期
        pub_time = None
        # 法A: URL 中的 /DD/MM/YYYY-
        date_match = re.search(r'/(\d{2})/(\d{2})/(\d{4})-', response.url)
        if date_match:
            d, m, y = date_match.groups()
            try:
                pub_time = datetime(year=int(y), month=int(m), day=int(d))
            except: pass
        
        # 法B: 页面上 a[href*="daywise.php?date="] 的文本 (如 31 Mar, 2026)
        if not pub_time:
            date_link = response.css('a[href*="daywise.php?date="]::text').get()
            if date_link:
                try:
                    # 尝试匹配 31 Mar, 2026 或 21 Feb, 2026
                    pub_time = datetime.strptime(date_link.strip(), '%d %b, %Y')
                except: pass
        
        if not pub_time:
            pub_time = datetime.now()

        # 3. 日期过滤
        if not self.filter_date(pub_time):
            return

        # 4. 提取正文
        # 文莱站的正文结构较平级，通常聚集在一系列 P 标签内
        paragraphs = response.css('body p::text, body div.post-content p::text, p *::text').getall()
        # 排除掉无关的简短文本 (如 'Leave a Comment')
        content = "\n\n".join([p.strip() for p in paragraphs if len(p.strip()) > 30])
        
        if not content:
            # 终极兜底方案
            content = response.xpath('string(//body)').get()
        
        if content:
            content = content.replace('\t', '').replace('\r', '').strip()

        item = {
            'url': response.url,
            'title': title,
            'content': content,
            'publish_time': pub_time,
            'author': 'BruDirect Brunei',
            'language': 'en',
            'section': 'National'
        }
        
        yield item
