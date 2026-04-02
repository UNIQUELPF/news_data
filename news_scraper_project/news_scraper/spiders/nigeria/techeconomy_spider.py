import scrapy
from bs4 import BeautifulSoup
from datetime import datetime
from news_scraper.spiders.base_spider import BaseNewsSpider

class NigeriaTechEconomySpider(BaseNewsSpider):
    name = 'ng_techeconomy'
    allowed_domains = ['techeconomy.ng']
    start_urls = ['https://techeconomy.ng/category/business/']
    
    # 继承 BaseNewsSpider，自动初始化 ng_techeconomy_news 表
    target_table = 'ng_techeconomy_news'
    
    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.0,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 4,
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        }
    }

    def start_requests(self):
        # JNews 架构翻页格式为 /page/N/
        # 回溯至 2026-01-01 约需 50-80 页
        for page in range(1, 81):
            url = self.start_urls[0] if page == 1 else f"{self.start_urls[0]}page/{page}/"
            yield scrapy.Request(url, callback=self.parse_list, meta={'page': page})

    def parse_list(self, response):
        # 获取 JNews 列表中的文章链接
        articles = response.css('.jeg_post_title a::attr(href)').getall()
        if not articles:
            articles = response.css('a.jeg_readmore::attr(href)').getall()

        for link in articles:
            full_url = response.urljoin(link)
            # 尼日利亚科技类文章通常发布较频繁，通过 URL 结构和元数据验证日期
            if full_url in self.scraped_urls:
                continue
            self.scraped_urls.add(full_url)
            yield scrapy.Request(full_url, callback=self.parse_article)

    def parse_article(self, response):
        item = {}
        item['url'] = response.url
        
        # 标题提取 (JNews 标准样式)
        title = response.css('h1.jeg_ad_article_title::text').get() or \
                response.css('.entry-header h1::text').get() or \
                response.xpath('//meta[@property="og:title"]/@content').get()
        item['title'] = title.strip() if title else 'TechEconomy Report'

        # 正文提取：定位 entry-content
        content_html = response.css('.entry-content').get() or response.css('.jeg_main_content').get()
        if content_html:
            soup = BeautifulSoup(content_html, 'html.parser')
            # 移除杂质
            for tag in soup(['script', 'style', 'div.jeg_ad', '.entry-pagination']):
                tag.decompose()
            
            # 提取所有段落
            paragraphs = []
            for p in soup.find_all('p'):
                text = p.get_text().strip()
                if len(text) > 40:
                    paragraphs.append(text)
            
            item['content'] = "\n\n".join(paragraphs)
        
        # 精准发布时间获取
        pub_time_str = response.xpath('//meta[@property="article:published_time"]/@content').get() or \
                       response.css('time::attr(datetime)').get()
        
        if pub_time_str:
            try:
                # 兼容 ISO 格式
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
        item['author'] = response.css('.jeg_meta_author a::text').get() or 'TechEconomy Desk'
        item['language'] = 'en' # 英语
        item['section'] = 'Tech & Business'

        if item.get('content') and len(item['content']) > 200:
            yield item
