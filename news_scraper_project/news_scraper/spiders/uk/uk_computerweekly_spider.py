import scrapy
import re
from datetime import datetime
from news_scraper.spiders.base_spider import BaseNewsSpider

class UkComputerweeklySpider(BaseNewsSpider):
    name = "uk_computerweekly"
    allowed_domains = ["computerweekly.com", "r.jina.ai"]
    target_table = "uk_computerweekly_news"

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "news_scraper.middlewares.CurlCffiMiddleware": 543,
            "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
        },
        "CURLL_CFFI_IMPERSONATE": "chrome120",
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0
    }

    use_curl_cffi = True

    def __init__(self, target_url=None, *args, **kwargs):
        super(UkComputerweeklySpider, self).__init__(*args, **kwargs)
        self.target_url = target_url # Optional param for single URL scraping

    def start_requests(self):
        """
        Production mode:
        If target_url is provided, scrape it.
        Otherwise, search for new links could be added here.
        By default, we implement the shadow proxy bypass logic.
        """
        if self.target_url:
            urls = [self.target_url]
        else:
            # Default empty start - relies on external scheduler or manual URL passing
            urls = []
            
        for url in urls:
            jina_url = f"https://r.jina.ai/{url}"
            yield scrapy.Request(jina_url, callback=self.parse_jina, meta={"original_url": url})

    def parse_jina(self, response):
        body = response.text
        
        # 1. Extract Title
        title_match = re.search(r'^Title:\s*(.*)$', body, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else ""
        
        # 2. Extract Date
        # Format often: 2026-03-31T05:30Z or text in Mardown
        date_match = re.search(r'^Published Time:\s*(.*)$', body, re.MULTILINE)
        pub_date = None
        if date_match:
            date_str = date_match.group(1).strip().split('+')[0].replace('Z', '')
            if len(date_str) == 16: date_str += ":00"
            try:
                pub_date = datetime.fromisoformat(date_str)
            except:
                # Backup regex for text-based dates
                text_date = re.search(r'([0-9]{1,2}\s+[A-Z][a-z]{2,9}\s+2026)', body)
                if text_date:
                    try: pub_date = datetime.strptime(text_date.group(1), "%d %B %Y")
                    except: pass
        
        if pub_date and not self.filter_date(pub_date):
            return

        # 3. Extract Content from Jina Markdown
        content_split = body.split("Markdown Content:")
        content = ""
        if len(content_split) > 1:
            content = content_split[1].strip()
            # Cleanup Markdown artifacts
            content = re.sub(r'!\[.*?\]\(.*?\)', '', content)
            content = re.sub(r'\n{3,}', '\n\n', content)

        if title and content:
            yield {
                "url": response.meta["original_url"],
                "title": title,
                "content": content,
                "publish_time": pub_date,
                "author": "Computer Weekly",
                "language": "en",
                "section": "IT News"
            }
