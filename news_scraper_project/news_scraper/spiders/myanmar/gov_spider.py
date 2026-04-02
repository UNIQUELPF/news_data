import scrapy
from bs4 import BeautifulSoup
from datetime import datetime
import re
from news_scraper.spiders.base_spider import BaseNewsSpider

class MyanmarGovSpider(BaseNewsSpider):
    name = 'mm_gov'
    allowed_domains = ['myanmar.gov.mm']
    start_urls = ['https://www.myanmar.gov.mm/news-media/news/latest-news']
    
    # 继承 BaseNewsSpider，自动初始化 mm_gov_news 表
    target_table = 'mm_gov_news'
    
    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.5,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 2,
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        }
    }

    def start_requests(self):
        # Liferay 系统的分页参数极其特殊
        base_param = "?_com_liferay_asset_publisher_web_portlet_AssetPublisherPortlet_INSTANCE_idasset354_cur="
        # 官方文档抓取通常需要较大的回溯深度，回溯至 2026-01-01
        for page in range(1, 40):
            url = f"{self.start_urls[0]}{base_param}{page}"
            yield scrapy.Request(url, callback=self.parse_list, meta={'page': page})

    def parse_list(self, response):
        # 获取 Liferay 生成的跳转链接
        articles = response.css('.asset-title a::attr(href)').getall()
        if not articles:
            # 备选选择器：小卡片样式
            articles = response.css('.smallcardstyle a::attr(href)').getall()

        for link in articles:
            if link and '/content/' in link:
                if link in self.scraped_urls:
                    continue
                self.scraped_urls.add(link)
                yield scrapy.Request(link, callback=self.parse_article)

    def parse_article(self, response):
        item = {}
        item['url'] = response.url
        
        # 官方标题提取
        title = response.css('h1.fontsize24::text').get() or response.css('.asset-content h2::text').get()
        item['title'] = title.strip() if title else 'Official News'

        # 正文提取：Liferay 的 asset-full-content 区域
        content_html = response.css('.asset-full-content').get() or response.css('.asset-content').get()
        if content_html:
            soup = BeautifulSoup(content_html, 'html.parser')
            # 移除导航和无关脚本
            for tag in soup(['script', 'style', '.portlet-title-text']):
                tag.decompose()
            
            # 清洗高价值官方段落
            paragraphs = []
            for p in soup.find_all(['p', 'div']):
                text = p.get_text().strip()
                # 剔除极短的噪音字符
                if len(text) > 30:
                    paragraphs.append(text)
            
            item['content'] = "\n\n".join(paragraphs)
        
        # 官方日期解析：通常在 fontsize18 或特定文本块中
        # 甚至可能需要从 URL 编码中猜测，但 Liferay 常会有 meta 标签
        pub_time_str = response.xpath('//meta[@property="article:published_time"]/@content').get()
        
        # 如果 meta 没有，尝试解析页面上的 Burmese 日期字符串（需转换）
        curr_time = datetime.now()
        if pub_time_str:
            try:
                pub_dt = datetime.fromisoformat(pub_time_str.replace('Z', '+00:00'))
                pub_time = pub_dt.replace(tzinfo=None)
            except:
                pub_time = curr_time
        else:
            # 官方站有时发布时间标注不规范，默认标记为抓取时间（暂定）
            pub_time = curr_time

        # 日期过滤逻辑 (继承自基类)
        if not self.filter_date(pub_time):
            return

        item['publish_time'] = pub_time
        item['author'] = 'Myanmar Government Portal'
        item['language'] = 'my' # 官方站默认为缅甸语，少量英语
        item['section'] = 'Latest News'

        if item.get('content') and len(item['content']) > 200:
            yield item
