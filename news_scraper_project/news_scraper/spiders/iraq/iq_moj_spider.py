import scrapy
from datetime import datetime
from news_scraper.spiders.base_spider import BaseNewsSpider

class IqMojSpider(BaseNewsSpider):
    name = "iq_moj"

    country_code = 'IRQ'

    country = '伊拉克'
    allowed_domains = ["moj.gov.iq"]
    start_urls = ["https://www.moj.gov.iq/news/"]
    
    use_curl_cffi = True
    
    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "news_scraper.middlewares.CurlCffiMiddleware": 543,
            "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
        },
        "CURLL_CFFI_IMPERSONATE": "chrome120",
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1
    }
    
    target_table = "iq_moj_news"

    def parse(self, response):
        # 提取符合 /view.ID 模式的新闻链接
        links = response.css('a[href^="/view."]::attr(href)').getall()
        self.logger.info(f"Listing Page: Found {len(links)} links on {response.url}")
        
        for link in links:
            yield response.follow(link, self.parse_article)
            
        # 翻页
        next_page = response.css('a.next-page::attr(href)').get()
        if next_page:
            yield response.follow(next_page, self.parse)

    def parse_article(self, response):
        title = response.css('h1.article-title::text').get("").strip()
        date_raw = response.css('span.meta-date::text').get("").strip()
        
        # 29/03/2026 - 02:07 صباحًا
        pub_date = None
        if date_raw:
            try:
                # 转换阿拉伯语 AM/PM
                date_norm = date_raw.replace('صباحًا', 'AM').replace('مساءً', 'PM')
                pub_date = datetime.strptime(date_norm, '%d/%m/%Y - %I:%M %p')
            except Exception as e:
                self.logger.debug(f"Date error: {e} for {date_raw}")

        # 日期过滤: 2026-01-01
        if pub_date and not self.filter_date(pub_date):
            return

        # 提取正文
        content_parts = response.css('div.article-content-container p::text, div.article-body p::text').getall()
        if not content_parts:
             content_parts = response.css('div.article-content-container ::text').getall()
             
        cleaned_content = "\n\n".join([p.strip() for p in content_parts if len(p.strip()) > 10])

        if cleaned_content:
            yield {
                "url": response.url,
                "title": title,
                "content": cleaned_content,
                "publish_time": pub_date,
                "author": "Ministry of Justice - Iraq",
                "language": "ar",
                "section": "News"
            }
