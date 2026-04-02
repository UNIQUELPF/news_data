import scrapy
import re
from datetime import datetime
from news_scraper.spiders.base_spider import BaseNewsSpider

class VnBaochinhphuSpider(BaseNewsSpider):
    name = "vn_baochinhphu"
    allowed_domains = ["baochinhphu.vn"]
    # category id 1027 is 'Kinh tế' (Economy)
    target_table = "vn_baochinhphu_news"

    def start_requests(self):
        # We start directly with the timeline AJAX which provides steady pagination
        # Page 1 is the landing, subsequent pages follow /timelinelist/1027/{p}.htm
        for p in range(1, 101): # Backfill up to 100 pages
            url = f"https://baochinhphu.vn/timelinelist/1027/{p}.htm"
            yield scrapy.Request(
                url, 
                callback=self.parse,
                headers={"Referer": "https://baochinhphu.vn/kinh-te.htm"}
            )

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "news_scraper.middlewares.CurlCffiMiddleware": 543,
            "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
        },
        "CURLL_CFFI_IMPERSONATE": "chrome120",
        "CONCURRENT_REQUESTS": 12,
        "DOWNLOAD_DELAY": 0.3
    }

    use_curl_cffi = True

    def parse(self, response):
        """
        Parse timeline AJAX responses
        """
        # Government site uses box-category-item or box-stream-item
        articles = response.css('div.box-category-item, div.box-stream-item')
        
        for article in articles:
            # The title and link are often in a.box-category-link-title or similar
            link_node = article.css('a.box-category-link-title, a.box-stream-link-title, a[data-type="title"]')
            link = link_node.attrib.get('href')
            if not link: continue
            if not link.startswith('http'):
                link = "https://baochinhphu.vn" + link

            # URL date hint discovery: indices 3-8 of the numeric part (YYMMDD)
            # E.g., ...102260402172140876.htm -> 260402 (Apr 2, 2026)
            match = re.search(r'(\d{18})', link)
            if match:
                id_part = match.group(1)
                date_hint = id_part[3:9] # Indices 3,4,5,6,7,8
                try:
                    dt = datetime.strptime(date_hint, "%y%m%d")
                    if not self.filter_date(dt):
                        continue
                except:
                    pass
            
            if link in self.scraped_urls:
                continue

            yield scrapy.Request(
                link, 
                callback=self.parse_article,
                headers={"Referer": "https://baochinhphu.vn/kinh-te.htm"}
            )

    def parse_article(self, response):
        # Extract title
        title = response.css('.detail-title::text').get()
        if not title:
            title = response.css('h1::text', 'title::text').get()
            
        # Extract date string
        # Format: 02/04/2026 17:21 (DD/MM/YYYY HH:mm)
        date_str = response.css('.detail-time::text').get()
        pub_date = None
        if date_str:
            try:
                clean_date = re.search(r'(\d{2}/\d{2}/\d{4})', date_str)
                if clean_date:
                    pub_date = datetime.strptime(clean_date.group(1), "%d/%m/%Y")
            except:
                pass

        if pub_date and not self.filter_date(pub_date):
            return

        # Extract content
        # .detail-content is the main container for Government news
        content_nodes = response.css('.detail-content p::text, .detail-content p span::text').getall()
        content = "\n".join([c.strip() for c in content_nodes if c.strip()])

        if not content:
            # Fallback for structured content
            content_nodes = response.css('div.detail-content div::text').getall()
            content = "\n".join([c.strip() for c in content_nodes if c.strip()])

        if title and content:
            yield {
                "url": response.url,
                "title": title.strip(),
                "content": content,
                "publish_time": pub_date,
                "author": "Vietnam Government",
                "language": "vi",
                "section": "Kinh tế"
            }
