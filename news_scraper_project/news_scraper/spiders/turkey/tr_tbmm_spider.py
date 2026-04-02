import scrapy
from datetime import datetime
from news_scraper.spiders.base_spider import BaseNewsSpider

class TrTbmmSpider(BaseNewsSpider):
    name = 'tr_tbmm'
    allowed_domains = ['tbmm.gov.tr']
    
    # 无限加载接口
    # 经调研，www.tbmm.gov.tr/meclis-haber/meclis 路由较 global 更加畅通
    base_url = 'https://www.tbmm.gov.tr/meclis-haber/meclis?pageIndex={}'
    
    def start_requests(self):
        yield scrapy.Request(
            self.base_url.format(0),
            callback=self.parse
        )

    # 数据库表名配置
    target_table = 'tr_tbmm_news'
    
    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'CONCURRENT_REQUESTS': 8, 
        'DOWNLOAD_DELAY': 1,
        'ROBOTSTXT_OBEY': False
    }

    def parse(self, response):
        # 精准匹配含有 Haber/Detay (新闻详情) 的 Id 链接
        links = response.css("a[href*='/Haber/Detay?Id=']::attr(href)").getall()
        current_page = response.meta.get('page', 0)
        self.logger.info(f"Page {current_page} - Captured {len(links)} links.")

        for link in set(links):
            yield response.follow(link, self.parse_article)

        # 只要当前页有数据且未翻过头，就继续翻页
        if links and current_page < 1000: 
            next_page = current_page + 1
            yield scrapy.Request(
                self.base_url.format(next_page),
                callback=self.parse,
                meta={'page': next_page}
            )

    def parse_article(self, response):
        # 1. 优先从元数据提取 (最抗干扰)
        title = response.css('meta[property="og:title"]::attr(content)').get()
        
        # 2. 备选方案: 强制递归剥离所有层级的文本
        if not title or len(title.strip()) < 2:
            # string() 会递归获取所有子孙节点的文本
            raw_text = response.xpath('string(//div[@id="haber-detay-baslik"])').get()
            if raw_text:
                # 剔除掉可能包含的日期行
                lines = [l.strip() for l in raw_text.split('\n') if l.strip()]
                # 剩下的最长的行通常就是标题
                if lines:
                    title = max(lines, key=len)
        
        if not title:
            title = response.css('title::text').get('').split('-')[0].strip()
            
        pub_time_str = response.css('div#haber-detay-saat-dakika::text').get('').strip()
        
        pub_time = None
        if pub_time_str:
            try:
                # 兼容格式: 2026-03-31 - 15:42
                clean_date = pub_time_str.split('-')
                if len(clean_date) >= 3:
                    date_part = "-".join(clean_date[:3]).strip()
                    time_part = clean_date[-1].strip()
                    pub_time = datetime.strptime(f"{date_part} {time_part}", "%Y-%m-%d %H:%M")
            except:
                pass

        if not pub_time:
            pub_time = datetime.now()
        
        # 调试: 打印提取结果
        self.logger.info(f"Checking article: {title} | Date: {pub_time} | URL: {response.url}")

        # 日期过滤
        if not self.filter_date(pub_time):
            self.logger.info(f"Filtered (Old): {pub_time} for {response.url}")
            return

        summary = response.css('div#haber-detay-ozet::text').get('').strip()
        body_parts = response.css('div#haber-detay-aciklama p::text, div#haber-detay-aciklama ::text').getall()
        content = "\n\n".join([p.strip() for p in body_parts if p.strip()])
        
        if summary:
            content = f"{summary}\n\n{content}"

        item = {
            'url': response.url,
            'title': title,
            'content': content,
            'publish_time': pub_time,
            'author': 'TBMM Official',
            'language': 'tr',
            'section': 'Official News'
        }
        
        self.logger.info(f"Yielding Valid Item: {title}")
        yield item
