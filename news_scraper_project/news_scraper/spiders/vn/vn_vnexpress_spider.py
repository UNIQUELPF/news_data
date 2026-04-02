import scrapy
import re
from datetime import datetime
from news_scraper.spiders.base_spider import BaseNewsSpider

class VnVnexpressSpider(BaseNewsSpider):
    name = "vn_vnexpress"
    allowed_domains = ["vnexpress.net"]
    start_urls = ["https://vnexpress.net/kinh-doanh"]
    target_table = "vn_vnexpress_news"

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "news_scraper.middlewares.CurlCffiMiddleware": 543,
            "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
        },
        "CURLL_CFFI_IMPERSONATE": "chrome120",
        "CONCURRENT_REQUESTS": 8,
        "DOWNLOAD_DELAY": 0.5
    }

    use_curl_cffi = True

    def parse(self, response):
        """
        Parse listing page with articles
        """
        articles = response.css('article.item-news')
        if not articles:
            # Try alternate selector if single page layout differs back in time
            articles = response.css('div.item-news')

        for article in articles:
            link_node = article.css('h2.title-news a, h3.title-news a')
            link = link_node.attrib.get('href')
            if not link: continue
            
            # Check timestamps from data-publishtime if available for quick filter
            pub_timestamp = article.attrib.get('data-publishtime')
            if pub_timestamp:
                try:
                    dt = datetime.fromtimestamp(int(pub_timestamp))
                    if not self.filter_date(dt):
                        continue
                except:
                    pass
            
            if link in self.scraped_urls:
                continue

            yield scrapy.Request(link, callback=self.parse_article)

        # Pagination: /kinh-doanh-p2, etc.
        current_page = 1
        page_match = re.search(r'-p(\d+)$', response.url.split('?')[0])
        if page_match:
            current_page = int(page_match.group(1))
        
        # Limit to reasonable depth for safety (e.g., 100 pages for Jan 2026 backfill)
        if len(articles) > 0 and current_page < 100:
            next_page = current_page + 1
            next_url = f"https://vnexpress.net/kinh-doanh-p{next_page}"
            yield scrapy.Request(next_url, callback=self.parse)

    def parse_article(self, response):
        # Extract title
        title = response.css('h1.title-detail::text').get()
        if not title:
            title = response.css('h1::text').get()
        
        # Extract date from meta
        date_str = response.css('meta[name="pubdate"]::attr(content)').get()
        if not date_str:
            date_str = response.css('meta[property="article:published_time"]::attr(content)').get()
            
        pub_date = None
        if date_str:
            # Example: 2026-03-31T16:05:09+07:00
            try:
                # Handle ISO format with timezone
                pub_date = datetime.fromisoformat(date_str.split('+')[0])
            except:
                pass
        
        if not pub_date:
            # Fallback text date in span.date
            # Example: Thứ ba, 31/3/2026, 16:05 (GMT+7)
            date_text = response.css('span.date::text').get()
            if date_text:
                match = re.search(r'(\d{1,2}/\d{1,2}/2026)', date_text)
                if match:
                    try:
                        pub_date = datetime.strptime(match.group(1), "%d/%m/%Y")
                    except:
                        pass

        if pub_date and not self.filter_date(pub_date):
            return

        # Extract content
        # FCK_detail is the main content container for VnExpress
        content_nodes = response.css('article.fck_detail p::text, article.fck_detail p span::text').getall()
        content = "\n".join([c.strip() for c in content_nodes if c.strip()])

        if not content:
            # Backup content selector
            content_nodes = response.css('div.fck_detail p::text').getall()
            content = "\n".join([c.strip() for c in content_nodes if c.strip()])

        if title and content:
            yield {
                "url": response.url,
                "title": title.strip(),
                "content": content,
                "publish_time": pub_date,
                "author": "VnExpress",
                "language": "vi",
                "section": "Kinh doanh"
            }
