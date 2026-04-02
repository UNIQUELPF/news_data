import scrapy
from datetime import datetime
import json
from news_scraper.spiders.base_spider import BaseNewsSpider

class GrNaftemporikiSpider(BaseNewsSpider):
    name = 'gr_naftemporiki'
    allowed_domains = ['naftemporiki.gr']
    
    # 航运报新闻大厅列表
    base_url = 'https://www.naftemporiki.gr/newsroom/page/{}/'
    start_urls = [base_url.format(1)]
    
    # 数据库配置 (Greece -> gr, Site -> naftemporiki)
    target_table = 'gr_naftemporiki_news'

    def parse(self, response):
        # 1. 提取文章链接
        # 选择器根据探测结果为 div.title a
        article_links = response.css('div.title a::attr(href)').getall()
        
        current_page = response.meta.get('page', 1)
        valid_items_count = 0
        
        for link in article_links:
            yield response.follow(link, self.parse_article)
            valid_items_count += 1

        # 2. 翻页逻辑: 只要当前页有文章且未达到安全阈值，继续翻页
        # 历史回溯至 2026/01/01
        if valid_items_count > 0 and current_page < 5000:
            next_page = current_page + 1
            yield scrapy.Request(
                self.base_url.format(next_page),
                callback=self.parse,
                meta={'page': next_page}
            )

    def parse_article(self, response):
        # 1. 提取发布时间 (ISO 格式优先)
        pub_time_raw = response.css('meta[property="article:published_time"]::attr(content)').get()
        if not pub_time_raw:
            # 兜底从 LD-JSON 提取
            try:
                ld_json = json.loads(response.xpath('//script[@type="application/ld+json" and contains(text(), "datePublished")]/text()').get())
                if isinstance(ld_json, list):
                    pub_time_raw = ld_json[0].get('datePublished')
                else:
                    pub_time_raw = ld_json.get('datePublished')
            except:
                pass

        if not pub_time_raw:
            return

        # 解析 ISO 时间 (例如 2026-03-31T19:37:08+03:00)
        try:
            # 兼容带时区偏移的情况
            pub_time = datetime.fromisoformat(pub_time_raw.split('+')[0])
        except:
            return

        # 2. 日期过滤 (2026-01-01 之后)
        if not self.filter_date(pub_time):
            return

        # 3. 提取标题和内容
        title = response.css('h1::text').get('').strip()
        content_parts = response.css('.post-content p::text, .post-content li::text').getall()
        content = "\n\n".join([p.strip() for p in content_parts if p.strip()])

        # 如果 content 为空，尝试更广的选择器
        if not content:
            content = "\n\n".join(response.css('article p::text').getall())

        item = {
            'url': response.url,
            'title': title,
            'content': content,
            'publish_time': pub_time,
            'author': 'Naftemporiki Newsroom',
            'language': 'el',
            'section': response.css('meta[property="article:section"]::attr(content)').get('News')
        }
        
        yield item
