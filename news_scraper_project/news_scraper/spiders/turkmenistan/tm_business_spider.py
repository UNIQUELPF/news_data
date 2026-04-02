import scrapy
from datetime import datetime
from news_scraper.spiders.base_spider import BaseNewsSpider

class TmBusinessSpider(BaseNewsSpider):
    name = 'tm_business'
    allowed_domains = ['business.com.tm']
    
    # URL for pagination containing the explicit API index
    base_url = 'https://business.com.tm/post/a/index?path=news&Post_sort=date_added.desc&page={}'
    start_urls = [base_url.format(1)]
    
    # 数据库表名配置 (Turkmenistan -> tm, Website -> business)
    target_table = 'tm_business_news'
    
    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'CONCURRENT_REQUESTS': 8,
        'DOWNLOAD_DELAY': 1,
        'ROBOTSTXT_OBEY': False
    }

    def parse(self, response):
        # 提取文章链接
        # The list page contains h4.entry-title -> a
        links = response.css('h4.entry-title a::attr(href)').getall()
        # Fallback if the layout changes: any link with /post/[id]/[slug]
        if not links:
            links = response.css('a[href*="/post/"]::attr(href)').getall()
        
        valid_links = []
        for link in set(links):
            # Check if it looks like an article detail link: /post/\d+/.*
            parts = link.split('/post/')
            if len(parts) > 1 and parts[1].split('/')[0].isdigit():
                valid_links.append(link)

        for link in valid_links:
            yield response.follow(link, self.parse_article)

        # 只要当前页有数据返回，就继续翻页
        if valid_links:
            current_page = response.meta.get('page', 1)
            if current_page < 1000: # 限制最大页数防止无限循环
                next_page = current_page + 1
                yield scrapy.Request(
                    self.base_url.format(next_page),
                    callback=self.parse,
                    meta={'page': next_page}
                )

    def parse_article(self, response):
        # 1. 提取标题
        title = response.css('h1::text, h1 *::text').getall()
        title = "".join(t.strip() for t in title if t.strip())
        
        # 2. 提取发布时间
        pub_time = None
        datetime_str = response.css('time::attr(datetime)').get()
        if datetime_str:
            try:
                # 格式例如: 2026-03-27T16:44:09+05:00
                # Python 3.7+ fromisoformat handles +05:00, or we replace Z
                datetime_str = datetime_str.replace('Z', '+00:00')
                pub_time = datetime.fromisoformat(datetime_str)
            except Exception as e:
                self.logger.warning(f"Date parsing failed for {response.url}: {e} on string {datetime_str}")

        if not pub_time:
            # 备选提取 (可能从 meta 标签获取)
            meta_date = response.css('meta[property="article:published_time"]::attr(content)').get()
            if meta_date:
                try:
                    pub_time = datetime.fromisoformat(meta_date.replace('Z', '+00:00'))
                except: pass

        if not pub_time:
            pub_time = datetime.now()

        # 3. 日期基准过滤 (Inherited from BaseNewsSpider)
        if not self.filter_date(pub_time):
            return

        # 4. 提取正文内容 (通常在 div.content 下的 p 标签)
        # 先抓取 p 标签的文本
        paragraphs = response.css('div.content p::text, div.content p *::text').getall()
        # 加入 fallback 去抓取所有的文本如果为空
        if not paragraphs:
            paragraphs = response.css('div.content ::text').getall()
        
        # 去重空白符并组合
        # 使用一个辅助方法来处理内联标签导致的破碎文本
        raw_text = response.xpath('string(//div[contains(@class, "content")])').get()
        if raw_text:
            lines = [line.strip() for line in raw_text.split('\n') if line.strip()]
            content = "\n\n".join(lines)
        else:
            content = "\n\n".join([p.strip() for p in paragraphs if p.strip()])

        item = {
            'url': response.url,
            'title': title,
            'content': content,
            'publish_time': pub_time,
            'author': 'Business.com.tm',
            'language': 'en',
            'section': 'News'
        }
        
        yield item
