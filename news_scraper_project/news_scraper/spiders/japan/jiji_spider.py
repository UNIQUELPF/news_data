import scrapy
from bs4 import BeautifulSoup
from datetime import datetime
import re
from news_scraper.spiders.base_spider import BaseNewsSpider

class JijiSpider(BaseNewsSpider):
    name = 'jp_jiji'

    country_code = 'JPN'

    country = '日本'
    allowed_domains = ['jiji.com']
    
    # 目标表名：jp_jiji_news
    target_table = 'jp_jiji_news'
    
    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.0,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 2,
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
            'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
        }
    }

    def start_requests(self):
        # 模式 1: Archive 回溯 (覆盖 2026-01-01 至今)
        # offset 0: 3月, 1: 2月, 2: 1月
        archives = [
            'https://www.jiji.com/jc/archives?g=eco_archive_0',
            'https://www.jiji.com/jc/archives?g=eco_archive_1',
            'https://www.jiji.com/jc/archives?g=eco_archive_2'
        ]
        for url in archives:
            # 每个月先抓前 10 页 (基本覆盖全月)
            for page in range(1, 11):
                page_url = f"{url}&p={page}"
                yield scrapy.Request(page_url, callback=self.parse_list)

        # 模式 2: 当前列表 (增量)
        yield scrapy.Request('https://www.jiji.com/jc/list?g=eco', callback=self.parse_list)

    def parse_list(self, response):
        # 提取文章链接: a[href*="/jc/article?k="]
        links = response.css('a[href*="/jc/article?k="]::attr(href)').getall()
        for link in links:
            # 过滤掉一些非文章链接 (Jiji 有时会有重复或侧边栏链接)
            if 'k=' not in link: continue
            
            full_url = response.urljoin(link)
            # 基础去重 (内存中)
            if full_url in self.scraped_urls:
                continue
            self.scraped_urls.add(full_url)
            
            yield scrapy.Request(full_url, callback=self.parse_article)

    def parse_article(self, response):
        item = {}
        item['url'] = response.url
        
        # 1. 标题提取
        title = response.css('.ArticleTitle h1::text').get() or \
                response.css('h1::text').get() or \
                response.xpath('//meta[@property="og:title"]/@content').get()
        item['title'] = title.strip() if title else ''

        # 2. 正文提取
        content_nodes = response.css('.ArticleText p::text').getall()
        if content_nodes:
            item['content'] = "\n\n".join([p.strip() for p in content_nodes if len(p.strip()) > 5])
        else:
            item['content'] = "".join(response.css('.ArticleText::text').getall()).strip()

        # 3. 发布时间提取 (2026年03月30日10時27分)
        pub_time_str = response.css('.ArticleDate::text').get() or \
                       response.xpath('//meta[@property="article:published_time"]/@content').get()
        
        pub_time = datetime.now()
        if pub_time_str:
            try:
                # 鲁棒性解析: 提取所有数字 [2026, 03, 30, 10, 27]
                nums = re.findall(r'\d+', pub_time_str)
                if len(nums) >= 5:
                    pub_time = datetime(int(nums[0]), int(nums[1]), int(nums[2]), int(nums[3]), int(nums[4]))
                elif len(nums) >= 3:
                    pub_time = datetime(int(nums[0]), int(nums[1]), int(nums[2]))
            except:
                pass

        # 4. 日期过滤 (2026-01-01 后)
        if not self.filter_date(pub_time):
            return

        item['publish_time'] = pub_time
        item['author'] = 'Jiji Press'
        item['language'] = 'ja'
        item['section'] = 'Economy'

        if item.get('content') and len(item['content']) > 50:
            yield item
