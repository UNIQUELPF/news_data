import scrapy
import json
from datetime import datetime
from news_scraper.spiders.base_spider import BaseNewsSpider

class NzNewsroomSpider(BaseNewsSpider):
    name = "nz_newsroom"

    country_code = 'NZL'

    country = '新西兰'
    allowed_domains = ["newsroom.co.nz"]
    start_urls = ["https://newsroom.co.nz/category/economy/"]
    
    use_curl_cffi = True
    
    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "news_scraper.middlewares.CurlCffiMiddleware": 543,
            "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
        },
        "CURLL_CFFI_IMPERSONATE": "chrome120",
        "CONCURRENT_REQUESTS": 4,
        "DOWNLOAD_DELAY": 1
    }
    
    target_table = "nz_newsroom_news"

    def parse(self, response):
        # 提取文章列表链接
        article_links = response.css('a[rel="bookmark"]::attr(href)').getall()
        self.logger.info(f"Listing Page: Found {len(article_links)} links on {response.url}")
        
        for link in article_links:
            yield response.follow(link, self.parse_article)
            
        # 翻页处理
        next_page = response.css('a.next.page-numbers::attr(href)').get()
        if next_page:
            yield response.follow(next_page, self.parse)

    def parse_article(self, response):
        # 1. 优先从 LD-JSON 提取发布日期
        pub_date = None
        ld_jsons = response.css('script[type="application/ld+json"]::text').getall()
        for raw in ld_jsons:
            try:
                data = json.loads(raw)
                graph = data.get('@graph', [data]) if isinstance(data, dict) else [data]
                for item in graph:
                    # 匹配文章类对象
                    if isinstance(item, dict) and item.get('@type') in ['NewsArticle', 'Article', 'BlogPosting']:
                        date_str = item.get('datePublished')
                        if date_str:
                            pub_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                            break
                if pub_date:
                    break
            except Exception:
                continue

        # 2. 兜底解析日期
        if not pub_date:
            date_meta = response.css('time.entry-date.published::attr(datetime)').get()
            if date_meta:
                try:
                    pub_date = datetime.fromisoformat(date_meta.replace('Z', '+00:00'))
                except Exception:
                    pass

        # 日期过滤: 2026-01-01
        if pub_date and not self.filter_date(pub_date):
            return

        # 3. 提取标题与正文
        title = response.css('h1.entry-title::text').get("").strip()
        if not title:
            title = response.css('meta[property="og:title"]::attr(content)').get("").strip()

        paragraphs = response.css('.entry-content p::text, .entry-content p *::text').getall()
        cleaned_content = "\n\n".join([p.strip() for p in paragraphs if len(p.strip()) > 30])

        if cleaned_content:
            yield {
                "url": response.url,
                "title": title,
                "content": cleaned_content,
                "publish_time": pub_date,
                "author": response.css('.author-name a::text').get("Newsroom"),
                "language": "en",
                "section": "Economy"
            }
