import scrapy
import re
from datetime import datetime
from urllib.parse import urljoin
from news_scraper.spiders.base_spider import BaseNewsSpider

class UkParliamentSpider(BaseNewsSpider):
    name = "uk_parliament"
    allowed_domains = ["parliament.uk", "r.jina.ai"]
    
    # 3 Parallel categories to cover 'Parliamentary news'
    start_urls = [
        "https://www.parliament.uk/business/news/parliament-government-and-politics/parliament/commons-news/?page=1",
        "https://www.parliament.uk/business/news/parliament-government-and-politics/parliament/lords-news/?page=1",
    ]
    
    target_table = "uk_parliament_news"
    
    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "news_scraper.middlewares.CurlCffiMiddleware": 543,
            "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
        },
        "CURLL_CFFI_IMPERSONATE": "chrome120",
        "CONCURRENT_REQUESTS": 4,
        "DOWNLOAD_DELAY": 1.0
    }
    
    use_curl_cffi = True

    def parse(self, response):
        """
        Parse listing page with cards
        """
        cards = response.css('a.card.card-content')
        if not cards:
            self.logger.info(f"No cards found on {response.url}")
            return

        for card in cards:
            link = card.attrib.get('href')
            if not link: continue
            full_url = urljoin(response.url, link)
            
            # Use Jina for bypass and detail extraction
            jina_url = f"https://r.jina.ai/{full_url}"
            yield scrapy.Request(
                jina_url, 
                callback=self.parse_article, 
                meta={"original_url": full_url}
            )

        # Pagination logic
        current_page = 1
        if "page=" in response.url:
            match = re.search(r'page=(\d+)', response.url)
            if match: current_page = int(match.group(1))
            
        # We check the 'Next' link or just increment if we found items
        if len(cards) > 0 and current_page < 50: # Limit safe depth for backfill
            next_page = current_page + 1
            next_url = re.sub(r'page=\d+', f'page={next_page}', response.url)
            yield scrapy.Request(next_url, callback=self.parse)

    def parse_article(self, response):
        body = response.text
        
        # 1. Extract Title
        title_match = re.search(r'^Title:\s*(.*)$', body, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else ""
        
        # 2. Extract Date (Parliament.uk uses Month Year or DD Month Year format in Markdown)
        date_match = re.search(r'^Published Time:\s*(.*)$', body, re.MULTILINE)
        pub_date = None
        if date_match:
            date_str = date_match.group(1).strip().split('+')[0].replace('Z', '')
            if len(date_str) == 16: date_str += ":00"
            try:
                pub_date = datetime.fromisoformat(date_str)
            except:
                pass
        
        if not pub_date:
            # Fallback to visual text-based date from Markdown
            # Pattern: 30 March 2026 or March 30, 2026
            text_date = re.search(r'([0-9]{1,2}\s+[A-Z][a-z]{2,8}\s+20[0-9]{2})', body)
            if text_date:
                try: 
                    pub_date = datetime.strptime(text_date.group(1), "%d %B %Y")
                except: 
                    pass

        if pub_date and not self.filter_date(pub_date):
            return

        # 3. Extract Content
        content_split = body.split("Markdown Content:")
        content = ""
        if len(content_split) > 1:
            content = content_split[1].strip()
            # Clean up jina artifacts
            content = re.sub(r'!\[.*?\]\(.*?\)', '', content)
            content = re.sub(r'\n{3,}', '\n\n', content)

        if title and content:
            # Detect section from URL
            section = "Commons" if "commons-news" in response.meta["original_url"] else "Lords"
            if "committee" in response.meta["original_url"]: section = "Committees"
            
            yield {
                "url": response.meta["original_url"],
                "title": title,
                "content": content,
                "publish_time": pub_date,
                "author": "UK Parliament",
                "language": "en",
                "section": section
            }
