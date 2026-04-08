import scrapy
import re
from datetime import datetime, timedelta
from news_scraper.spiders.base_spider import BaseNewsSpider

class EeErrSpider(BaseNewsSpider):
    name = "ee_err"
    allowed_domains = ["news.err.ee"]
    start_urls = ["https://news.err.ee/k/business"]
    target_table = "ee_err_news"

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "news_scraper.middlewares.CurlCffiMiddleware": 543,
            "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
        },
        "CURLL_CFFI_IMPERSONATE": "chrome120",
        "CONCURRENT_REQUESTS": 4,
        "DOWNLOAD_DELAY": 0.8
    }

    use_curl_cffi = True

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(
                url, 
                callback=self.parse,
                meta={"playwright": True}
            )

    def parse(self, response):
        """
        Parse listing page with Playwright rendering: https://news.err.ee/k/business
        """
        articles = response.css('.category-item')
        for article in articles:
            link_node = article.css('p.category-news-header a')
            link = link_node.attrib.get('href')
            if not link:
                continue
            if not link.startswith('http'):
                link = "https://news.err.ee" + link

            if link in self.scraped_urls:
                continue

            yield scrapy.Request(
                link, 
                callback=self.parse_article,
                meta={"playwright": True}
            )

    def parse_article(self, response):
        # Title
        title = response.css('h1::text').get()
        if not title:
            title = response.css('title::text').get()
        
        # Date processing from rendered DOM: time.pubdate
        # Priority 1: datetime attribute (ISO 8601: 2026-03-25T17:24:00+02:00)
        # Priority 2: text content (25.03.2026 23:24)
        iso_date = response.css('time.pubdate::attr(datetime)').get()
        date_str = response.css('time.pubdate::text').get()
        
        pub_date = None
        if iso_date:
            try:
                # 2026-03-25T17:24:00+02:00 -> 2026-03-25 17:24:00
                pub_date = datetime.fromisoformat(iso_date.replace('Z', '+00:00'))
            except Exception:
                pass
        
        if not pub_date and date_str:
            date_str = date_str.strip()
            try:
                if "Yesterday" in date_str or "yesterday" in date_str.lower():
                    dt = datetime.now() - timedelta(days=1)
                    time_match = re.search(r'(\d{2}:\d{2})', date_str)
                    if time_match:
                        h, m = map(int, time_match.group(1).split(':'))
                        pub_date = dt.replace(hour=h, minute=m, second=0, microsecond=0)
                    else:
                        pub_date = dt
                else:
                    match = re.search(r'(\d{2}\.\d{2}\.(\d{4}|\d{2}))', date_str)
                    if match:
                        raw_date = match.group(1)
                        if len(raw_date.split('.')[-1]) == 4:
                            pub_date = datetime.strptime(raw_date, "%d.%m.%Y")
                        else:
                            pub_date = datetime.strptime(raw_date, "%d.%m.%y")
            except Exception as e:
                self.logger.warning(f"Could not parse date '{date_str}': {e}")

        if pub_date and not self.filter_date(pub_date):
            return

        content_nodes = response.css('.text p::text, .text p span::text, .text div.leade::text').getall()
        content = "\n".join([c.strip() for c in content_nodes if c.strip()])

        if title and content:
            yield {
                "url": response.url,
                "title": title.strip(),
                "content": content,
                "publish_time": pub_date,
                "author": "ERR Estonia",
                "language": "en",
                "section": "Business"
            }
