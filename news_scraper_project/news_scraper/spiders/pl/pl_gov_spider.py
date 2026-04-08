import scrapy
from datetime import datetime
from news_scraper.spiders.base_spider import BaseNewsSpider

class PlGovSpider(BaseNewsSpider):
    name = "pl_gov"
    allowed_domains = ["www.gov.pl"]
    start_urls = ["https://www.gov.pl/web/premier/wydarzenia?page=1"]
    target_table = "pl_gov_news"

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "news_scraper.middlewares.CurlCffiMiddleware": 543,
            "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
        },
        "CURLL_CFFI_IMPERSONATE": "chrome120",
        "CONCURRENT_REQUESTS": 4, 
        "DOWNLOAD_DELAY": 1.2,
        "PLAYWRIGHT_LAUNCH_OPTIONS": {"headless": True}
    }

    use_curl_cffi = True

    def parse(self, response):
        """
        Parse listing page: https://www.gov.pl/web/premier/wydarzenia?page=1
        """
        # Precise selector for gov.pl cards
        links = response.css('div.art-prev ul li .title a::attr(href)').getall()
        if not links:
            links = response.css('a[href*="/web/premier/"]::attr(href)').getall()

        found_any = False
        for link in links:
            if not link.startswith('http'):
                link = "https://www.gov.pl" + link
            
            # Filter non-relevant links
            if '/web/premier/wydarzenia' in link or '/web/' not in link or '?page' in link:
                 continue

            if link in self.scraped_urls:
                continue
            
            found_any = True
            yield scrapy.Request(
                link, 
                callback=self.parse_article,
                meta={"playwright": True}
            )

        # Pagination logic
        if found_any:
            current_page = 1
            if 'page=' in response.url:
                try:
                    current_page = int(response.url.split('page=')[-1].split('&')[0])
                except ValueError:
                    pass
            
            if current_page < 300: 
                next_page_url = f"https://www.gov.pl/web/premier/wydarzenia?page={current_page + 1}"
                yield scrapy.Request(next_page_url, callback=self.parse)

    def parse_article(self, response):
        # Improved title extraction
        title = response.css('.article-header .title::text').get()
        if not title:
             title = response.css('h2.title::text, h2::text, .article-title::text').get()
        if not title:
            title = response.css('title::text').get()
        
        # Date extraction (DD.MM.YYYY)
        date_str = response.css('p.event-date::text, .date::text, .article-header .date::text').get()
        if not date_str:
             import re
             raw_text = response.text
             match = re.search(r'(\d{2}\.\d{2}\.\d{4})', raw_text)
             if match:
                 date_str = match.group(1)

        pub_date = None
        if date_str:
            try:
                pub_date = datetime.strptime(date_str.strip(), "%d.%m.%Y")
            except Exception as e:
                self.logger.warning(f"Could not parse Polish date '{date_str}': {e}")

        # Date filtering (default 2026-01-01)
        if pub_date and not self.filter_date(pub_date):
             return

        # Aggregated content extraction from gov.pl structured article
        # p.intro (Lead) + .editor-content p (Body)
        intro = response.css('p.intro::text').get() or ""
        body_nodes = response.css('.editor-content p::text, .editor-content li::text').getall()
        body = "\n".join([b.strip() for b in body_nodes if b.strip()])
        
        content = intro.strip() + "\n" + body
        content = content.strip()

        # Fallback for older or different governmental layouts
        if not content:
             nodes = response.css('article#main-content p::text, article#main-content div::text').getall()
             content = "\n".join([n.strip() for n in nodes if n.strip() and len(n.strip()) > 10])

        if title and content and len(content) > 20:
            self.logger.info(f"Target Acquired: {response.url} (Date: {pub_date})")
            yield {
                "url": response.url,
                "title": title.strip(),
                "content": content,
                "publish_time": pub_date,
                "author": "Kancelaria Prezesa Rady Ministrów (KPRM)",
                "language": "pl",
                "section": "Government Announcements"
            }
        else:
             self.logger.warning(f"Field missing for {response.url}: Title={bool(title)}, ContentLen={len(content)}")
