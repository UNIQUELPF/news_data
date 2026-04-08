import scrapy
from datetime import datetime
from news_scraper.spiders.base_spider import BaseNewsSpider

class BgGovSpider(BaseNewsSpider):
    name = "bg_gov"
    allowed_domains = ["www.gov.bg"]
    start_urls = ["https://www.gov.bg/bg/prestsentar/novini?page=1"]
    target_table = "bg_gov_news"

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
        Parse listing page: https://www.gov.bg/bg/prestsentar/novini?page=1
        """
        # Select all unique government news links
        # Looking for links containing /bg/prestsentar/novini/
        links = response.css('a[href*="/bg/prestsentar/novini/"]::attr(href)').getall()
        # Deduplicate
        urls = []
        for l in links:
            if not l.startswith('http'):
                l = "https://www.gov.bg" + l
            if l not in urls and '/bg/prestsentar/novini/' in l and l != "https://www.gov.bg/bg/prestsentar/novini":
                urls.append(l)

        found_any = False
        for url in urls:
            # Persistent memory fingerprint check
            if url in self.scraped_urls:
                continue
            
            found_any = True
            yield scrapy.Request(
                url, 
                callback=self.parse_article
            )

        # Pagination logic
        if found_any:
            current_page = 1
            if 'page=' in response.url:
                try:
                    current_page = int(response.url.split('page=')[-1])
                except ValueError:
                    pass
            
            if current_page < 100: 
                next_page_url = f"https://www.gov.bg/bg/prestsentar/novini?page={current_page + 1}"
                yield scrapy.Request(next_page_url, callback=self.parse)

    def parse_article(self, response):
        # Title 
        title = response.css('h1::text').get()
        if not title:
            title = response.css('title::text').get()
        
        # Date processing (Bulgarian Format: 02.04.2026)
        # Often the date is in the first <p> or a specific div
        date_str = response.css('.view p:first-of-type::text').get()
        if not date_str or '.' not in date_str:
            # Try to find a date pattern in any p tag in case layout shifts
            for p in response.css('.view p::text').getall():
                if '.' in p and len(p.strip()) >= 10:
                    date_str = p.strip()
                    break

        pub_date = None
        if date_str:
            try:
                # DD.MM.YYYY
                import re
                match = re.search(r'(\d{2}\.\d{2}\.\d{4})', date_str)
                if match:
                    pub_date = datetime.strptime(match.group(1), "%d.%m.%Y")
            except Exception as e:
                self.logger.warning(f"Could not parse Bulgarian date '{date_str}': {e}")

        # Date filtering (default 2026-01-01)
        if pub_date and not self.filter_date(pub_date):
            return

        # Content extraction from government page structure
        content_nodes = response.css('.view.col-lg-12 p::text, .view.col-lg-12 li::text').getall()
        # Clean nodes
        content = "\n".join([c.strip() for c in content_nodes if c.strip() and len(c.strip()) > 5])

        if title and content:
            yield {
                "url": response.url,
                "title": title.strip(),
                "content": content,
                "publish_time": pub_date,
                "author": "Bulgarian Government",
                "language": "bg",
                "section": "Press Center"
            }
