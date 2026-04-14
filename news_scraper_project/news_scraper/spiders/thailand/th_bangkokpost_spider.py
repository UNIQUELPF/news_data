import scrapy
import json
from datetime import datetime
from news_scraper.spiders.base_spider import BaseNewsSpider

class ThBangkokPostSpider(BaseNewsSpider):
    name = 'th_bangkokpost'

    country_code = 'THA'

    country = '泰国'
    allowed_domains = ['bangkokpost.com']
    
    # 列表页配置
    start_url = 'https://www.bangkokpost.com/business/general'
    
    def start_requests(self):
        yield scrapy.Request(
            self.start_url,
            meta={
                "playwright": True,
                "playwright_include_page": True,
                "playwright_page_init_callback": self.block_resources,
            },
            callback=self.parse
        )

    async def block_resources(self, page, request):
        """加速渲染：屏蔽广告、图片及视频资源"""
        if request.resource_type in ["image", "media", "font", "stylesheet"]:
            await request.abort()
            return
        # 屏蔽可能的广告域名
        if "googletagservices" in request.url or "google-analytics" in request.url:
            await request.abort()
            return

    # 数据库表名配置
    target_table = 'th_bangkokpost_news'
    
    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'CONCURRENT_REQUESTS': 8,
        'DOWNLOAD_DELAY': 1,
        'PLAYWRIGHT_LAUNCH_OPTIONS': {'headless': True},
    }

    async def parse(self, response):
        page = response.meta["playwright_page"]
        
        # 初始抓取
        links = response.css('h3 a::attr(href)').getall()
        for link in links:
            if '/business/general/' in link:
                yield response.follow(link, self.parse_article)

        # 模拟点击翻页逻辑 (2026/1/1 全量需求)
        # 我们在这里点击 MORE 次数，直到检测到日期到达断点或达到最大翻页
        for _ in range(30):  # 估计 30 次点击可以覆盖到 2026/1/1
            try:
                # 检查 MORE 按钮是否存在并可点击
                more_button = await page.wait_for_selector('#page--link a', timeout=5000)
                if more_button:
                    await more_button.click()
                    await page.wait_for_timeout(2000) # 等待渲染
                    
                    # 重新提取新内容
                    content = await page.content()
                    new_selector = scrapy.Selector(text=content)
                    new_links = new_selector.css('h3 a::attr(href)').getall()
                    for link in new_links:
                        if '/business/general/' in link:
                            yield response.follow(link, self.parse_article)
                else:
                    break
            except Exception as e:
                self.logger.info(f"Stop clicking MORE: {e}")
                break
        
        await page.close()

    def parse_article(self, response):
        # 1. 优先从私有元数据提取 (最准确)
        pub_time = None
        date_str = response.css('meta[name="lead:published_at"]::attr(content)').get()
        if date_str:
            try:
                # 格式: 2026-03-31T01:01:00+07:00
                pub_time = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            except:
                pass

        # 2. 备选方案: 从标准 meta 标签提取
        if not pub_time:
            date_str = response.css('meta[property="article:published_time"]::attr(content)').get()
            if date_str:
                try:
                    pub_time = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                except:
                    pass

        # 3. 兜底方案: 解析可见文本 "PUBLISHED : 31 Mar 2026 at 01:01"
        if not pub_time:
            text_date = response.css('.article-info--col > p::text').get('')
            # 正则匹配 31 Mar 2026
            match = re.search(r'(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})', text_date)
            if match:
                d, m_str, y = match.groups()
                months = {
                    'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
                    'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
                }
                m = months.get(m_str)
                if m:
                    try:
                        pub_time = datetime(int(y), m, int(d))
                    except:
                        pass

        # 4. 深度兜底: 遍历所有 LD+JSON
        if not pub_time:
            ld_jsons = response.css('script[type="application/ld+json"]::text').getall()
            for ld in ld_jsons:
                try:
                    data = json.loads(ld)
                    if isinstance(data, list): data = data[0]
                    ds = data.get('datePublished')
                    if ds:
                        pub_time = datetime.fromisoformat(ds.replace('Z', '+00:00'))
                        break
                except:
                    continue

        # 5. 极度兜底: 使用当前时间
        if not pub_time:
            pub_time = datetime.now()

        # 6. 日期过滤
        if not self.filter_date(pub_time):
            return

        # 7. 提取内容
        title = response.css('h1::text').get('').strip()
        if not title:
            title = response.css('title::text').get('').replace(' - Bangkok Post', '').strip()

        paragraphs = response.css('.article-content p::text').getall()
        content = "\n\n".join([p.strip() for p in paragraphs if p.strip()])

        author = response.css('meta[name="author"]::attr(content)').get() or 'Bangkok Post'

        item = {
            'url': response.url,
            'title': title,
            'content': content,
            'publish_time': pub_time,
            'author': author,
            'language': 'en',
            'section': 'Business/General'
        }
        
        yield item
