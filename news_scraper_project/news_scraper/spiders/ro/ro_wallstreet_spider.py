import scrapy
import re
from datetime import datetime
from news_scraper.spiders.base_spider import BaseNewsSpider

class RoWallstreetSpider(BaseNewsSpider):
    name = "ro_wallstreet"

    country_code = 'ROU'

    country = '罗马尼亚'
    allowed_domains = ["www.wall-street.ro"]
    start_urls = ["https://www.wall-street.ro/articol/economie-and-finante/index.html"]
    target_table = "ro_wallstreet_news"

    # Romanian months mapping (abbreviated/full)
    MONTHS_RO = {
        "ian.": 1, "ianuarie": 1,
        "feb.": 2, "februarie": 2,
        "mar.": 3, "martie": 3,
        "apr.": 4, "aprilie": 4,
        "mai": 5, 
        "iun.": 6, "iunie": 6,
        "iul.": 7, "iulie": 7,
        "aug.": 8, "august": 8,
        "sep.": 9, "septembrie": 9,
        "oct.": 10, "octombrie": 10,
        "noi.": 11, "noiembrie": 11,
        "dec.": 12, "decembrie": 12
    }

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "news_scraper.middlewares.CurlCffiMiddleware": 543,
            "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
        },
        "CURLL_CFFI_IMPERSONATE": "chrome120",
        "CONCURRENT_REQUESTS": 8, 
        "DOWNLOAD_DELAY": 0.5,
    }

    use_curl_cffi = True

    def parse(self, response):
        """
        Parse listing page: https://www.wall-street.ro/articol/economie-and-finante/index.html
        """
        # Select article items
        articles = response.css('a.article-wrapper')
        found_any = False
        
        for article in articles:
            link = article.css('::attr(href)').get()
            if not link: continue
            
            if not link.startswith('http'):
                link = "https://www.wall-street.ro" + link

            if link in self.scraped_urls:
                continue

            # Title in h4 inside the a wrapper
            title = article.css('h4::text').get()
            
            found_any = True
            yield scrapy.Request(
                link, 
                callback=self.parse_article,
                meta={"title": title}
            )

        # Pagination logic: ?page=X
        if found_any:
            current_page = 1
            if '?page=' in response.url:
                try:
                    match = re.search(r'page=(\d+)', response.url)
                    if match: current_page = int(match.group(1))
                except: pass
            
            if current_page < 150: # Safeguard
                next_page_url = f"https://www.wall-street.ro/articol/economie-and-finante/index.html?page={current_page + 1}"
                yield scrapy.Request(next_page_url, callback=self.parse)

    def parse_article(self, response):
        title = response.meta.get("title") or response.css('h1.mb-0::text').get()
        if not title:
            title = response.css('title::text').get()
        
        # Publish time: .article-meta .date (e.g., "17 Mar. 2026")
        date_str = response.css('.article-meta .date::text').get()
        pub_date = None
        if date_str:
            try:
                # 17 Mar. 2026
                date_str = date_str.strip().lower()
                match = re.search(r'(\d{1,2})\s+([a-z\.]+)\s+(\d{4})', date_str)
                if match:
                    day = int(match.group(1))
                    month_name = match.group(2).strip('.')
                    year = int(match.group(3))
                    
                    # Try to match the key in MONTHS_RO (re-adding dot if needed)
                    # The mapping handles cases with and without dot if needed, 
                    # but let's try direct matches
                    if month_name in self.MONTHS_RO:
                        pub_date = datetime(year, self.MONTHS_RO[month_name], day)
                    elif (month_name + '.') in self.MONTHS_RO:
                        pub_date = datetime(year, self.MONTHS_RO[month_name + '.'], day)
            except Exception:
                 self.logger.warning(f"RO_DATE Parse failed: {date_str}")

        if pub_date and not self.filter_date(pub_date):
            return

        # Body: .article-content
        content_nodes = response.css('.article-content p::text, .article-content div::text').getall()
        content = "\n".join([c.strip() for c in content_nodes if len(c.strip()) > 30])

        if title and len(content) > 100:
            yield {
                "url": response.url,
                "title": title.strip(),
                "content": content,
                "publish_time": pub_date,
                "author": "Wall-Street.ro",
                "language": "ro",
                "section": "Economy"
            }
