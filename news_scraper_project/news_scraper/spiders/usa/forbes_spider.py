import json
from datetime import datetime

import scrapy
from bs4 import BeautifulSoup
from news_scraper.utils import get_incremental_state


class USAForbesSpider(scrapy.Spider):
    name = 'usa_forbes'

    country_code = 'USA'

    country = '美国'
    allowed_domains = ['forbes.com']
    start_urls = ['https://www.forbes.com/money/']
    
    target_table = 'usa_forbes_news'
    
    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.0,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 8,
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        }
    }

    def __init__(self, start_date='2026-01-01', *args, **kwargs):
        super(USAForbesSpider, self).__init__(*args, **kwargs)
        self.cutoff_date = datetime.strptime(start_date, '%Y-%m-%d')
        self.scraped_urls = set()
        self.init_db()

    def init_db(self):
        try:
            state = get_incremental_state(
                getattr(self, "settings", None),
                spider_name=self.name,
                table_name=self.target_table,
                default_cutoff=self.cutoff_date,
                full_scan=False,
            )
            self.cutoff_date = state["cutoff_date"]
            self.scraped_urls = state["scraped_urls"]
        except Exception as e:
            self.logger.error(f"DB init error: {e}")

    def iter_start_requests(self):
        # 1. 第一步：抓取首页 HTML 上的首批文章
        yield scrapy.Request(self.start_urls[0], callback=self.parse_list)

    def start_requests(self):
        yield from self.iter_start_requests()

    async def start(self):
        for request in self.iter_start_requests():
            yield request

    def parse_list(self, response):
        # 从 Next.js 的 JSON 脚本中直接提取
        data_script = response.xpath('//script[@id="__NEXT_DATA__"]/text()').get()
        if data_script:
            try:
                json.loads(data_script)
                # 提取首页推荐列表
                # ... 示例中使用选择器
            except:
                pass
        
        # 兜底：使用 CSS 选择器
        for a in response.css('a.kZ_L0i_J::attr(href)'): # Forbes 常见类别选择器
            link = a.get()
            if link and '/202' in link:
                yield scrapy.Request(response.urljoin(link), callback=self.parse_article)

    def request_api(self, start):
        # API 结构：基于 offset (start) & size
        api_url = f"https://www.forbes.com/simple-data/channel/money/?start={start}&size=50"
        yield scrapy.Request(
            api_url,
            callback=self.parse_api_json,
            meta={'start': start},
            dont_filter=True,
            handle_httpstatus_list=[403],
        )

    def parse_api_json(self, response):
        if response.status == 403:
            self.logger.info("Forbes simple-data API returned 403, skipping API pagination fallback.")
            return

        try:
            data = json.loads(response.text)
            # Forbes API 的结构通常是 list 或结果数组
            articles = data if isinstance(data, list) else data.get('articles', [])
            
            if not articles:
                return

            last_date = None
            for art in articles:
                uri = art.get('uri') or art.get('url')
                if not uri: continue
                
                # 时间判断 "2026-01-25..."
                # Forbes API 会直接提供时间戳或 date 字段
                pub_ts = art.get('date') or art.get('published_date')
                if pub_ts:
                    if isinstance(pub_ts, int):
                        pub_dt = datetime.fromtimestamp(pub_ts / 1000)
                    else:
                        try:
                            pub_dt = datetime.fromisoformat(pub_ts.replace('Z', '+00:00'))
                        except:
                            pub_dt = datetime.now()
                else:
                    pub_dt = datetime.now()
                
                last_date = pub_dt.replace(tzinfo=None)
                
                if last_date < self.cutoff_date:
                    self.logger.info("Reached start date, stopping Forbes pagination.")
                    return

                yield scrapy.Request(response.urljoin(uri), callback=self.parse_article, meta={'meta_date': last_date})

            # 继续翻页
            next_start = response.meta['start'] + 50
            if last_date and last_date >= self.cutoff_date:
                yield from self.request_api(next_start)
        except Exception as e:
            self.logger.error(f"Forbes API error: {e}")

    def parse_article(self, response):
        if response.url in self.scraped_urls:
            return
        self.scraped_urls.add(response.url)

        item = {}
        item['url'] = response.url
        item['title'] = response.css('h1.fs-headline::text').get() or response.xpath('//meta[@property="og:title"]/@content').get()
        
        # 正文提取
        content_html = response.css('div.article-body-container').get() or response.css('.article-body').get()
        if content_html:
            soup = BeautifulSoup(content_html, 'html.parser')
            # 剔除噪音
            for tag in soup(['script', 'style', 'aside', 'button', 'ul.related-content']):
                tag.decompose()
            
            # 清理文本
            text = soup.get_text(separator='\n')
            lines = [line.strip() for line in text.splitlines() if line.strip() and len(line.strip()) > 30]
            item['content'] = '\n\n'.join(lines)
        
        # 发布日期
        pub_time = response.meta.get('meta_date')
        if not pub_time:
            # 尝试从 URL 提取 /2026/03/24/
            import re
            match = re.search(r'/(\d{4})/(\d{2})/(\d{2})/', response.url)
            if match:
                pub_time = datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)))
            else:
                pub_time = datetime.now()

        item['publish_time'] = pub_time
        item['author'] = response.css('a.author-name--desktop::text').get() or 'Forbes'
        item['language'] = 'en'
        item['section'] = 'Money'

        if item.get('content') and len(item['content']) > 100:
            yield item
