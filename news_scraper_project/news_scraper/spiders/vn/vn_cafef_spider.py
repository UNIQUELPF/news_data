import scrapy
import re
from datetime import datetime
from news_scraper.spiders.base_spider import BaseNewsSpider

class VnCafefSpider(BaseNewsSpider):
    name = "vn_cafef"
    allowed_domains = ["cafef.vn"]
    # category id 18836 is 'Doanh nghiệp'
    target_table = "vn_cafef_news"

    def start_requests(self):
        # We start directly with the AJAX timeline which is more reliable than the 302ing main page
        for p in range(1, 101): # Backfill up to 100 pages (~3000 items)
            url = f"https://cafef.vn/timelinelist/18836/{p}.chn"
            yield scrapy.Request(
                url, 
                callback=self.parse,
                headers={"Referer": "https://cafef.vn/doanh-nghiep.chn"}
            )

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "news_scraper.middlewares.CurlCffiMiddleware": 543,
            "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
        },
        "CURLL_CFFI_IMPERSONATE": "chrome120",
        "CONCURRENT_REQUESTS": 16,
        "DOWNLOAD_DELAY": 0.2
    }

    use_curl_cffi = True

    def parse(self, response):
        """
        Parse AJAX timeline pages
        """
        # AJAX snippets use div.tlitem
        articles = response.xpath('//div[contains(@class, "tlitem")] | //li[contains(@class, "tlitem")]')
        
        for article in articles:
            link = article.xpath('.//h3/a/@href').get()
            if not link: continue
            if not link.startswith('http'):
                link = "https://cafef.vn" + link

            # URL date hint discovery: indices 3-8 of the numeric part
            # E.g., ...188260331114033374.chn -> 260331 (Mar 31, 2026)
            match = re.search(r'(\d{18})', link)
            if match:
                id_part = match.group(1)
                date_hint = id_part[3:9]
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
                headers={"Referer": "https://cafef.vn/doanh-nghiep.chn"}
            )

    def parse_article(self, response):
        # Extract title
        title = response.css('h1.title::text').get()
        if not title:
            title = response.css('h1::text', 'title::text').get()
            
        # Extract date
        date_str = response.css('span.pdate::text').get()
        pub_date = None
        if date_str:
            try:
                # 31-03-2026 - 11:42 AM
                clean_date = re.search(r'(\d{2}-\d{2}-\d{4})', date_str)
                if clean_date:
                    pub_date = datetime.strptime(clean_date.group(1), "%d-%m-%Y")
            except:
                pass

        if pub_date and not self.filter_date(pub_date):
            return

        # Extract content
        content_nodes = response.css('.totalcontentdetail p::text, .totalcontentdetail p span::text').getall()
        content = "\n".join([c.strip() for c in content_nodes if c.strip()])

        if not content:
            content_nodes = response.css('div.content p::text').getall()
            content = "\n".join([c.strip() for c in content_nodes if c.strip()])

        if title and content:
            yield {
                "url": response.url,
                "title": title.strip(),
                "content": content,
                "publish_time": pub_date,
                "author": "CafeF",
                "language": "vi",
                "section": "Doanh nghiệp"
            }
