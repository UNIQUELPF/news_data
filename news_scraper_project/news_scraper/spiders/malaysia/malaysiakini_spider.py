import json
from datetime import datetime

import scrapy
from news_scraper.spiders.smart_spider import SmartSpider
from bs4 import BeautifulSoup
from news_scraper.items import NewsItem


class MalaysiakiniSpider(SmartSpider):
    name = "malaysia_malaysiakini"

    country_code = "MYS"

    country = "马来西亚"
    language = "en"
    source_timezone = "Asia/Kuala_Lumpur"
    start_date = "2026-01-01"
    allowed_domains = ["malaysiakini.com"]
    
    # Use CurlCffi for stable and fast JSON fetching
    use_curl_cffi = True

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 0.5,
        'CONCURRENT_REQUESTS': 16,
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
    }




    def iter_start_requests(self):
        # 1. Get BuildID and Max SID
        yield scrapy.Request("https://www.malaysiakini.com/en/latest/news", callback=self.parse_init)

    def start_requests(self):
        yield from self.iter_start_requests()

    async def start(self):
        for request in self.iter_start_requests():
            yield request

    def parse_init(self, response):
        script_text = response.xpath('//script[@id="__NEXT_DATA__"]/text()').get()
        if not script_text:
            self.logger.error("Could not find __NEXT_DATA__ script")
            return

        try:
            data = json.loads(script_text)
            self.build_id = data.get('buildId')
            self.logger.info(f"Extracted BuildID: {self.build_id}")
            
            # Use a slightly stable API to get the current Max SID
            # limit=1 works
            yield scrapy.Request(
                "https://www.malaysiakini.com/api/en/latest/news/1?limit=1",
                callback=self.generate_sid_requests
            )
        except Exception as e:
            self.logger.error(f"Error parsing __NEXT_DATA__: {e}")

    def generate_sid_requests(self, response):
        try:
            data = json.loads(response.text)
            stories = data.get('stories', [])
            if not stories:
                # If first page is empty, it might be a block. Try to just guess a reasonable high SID
                max_sid = 771500
            else:
                max_sid = stories[0].get('sid', 771500)
                
            self.logger.info(f"Starting SID iteration from {max_sid} downwards")
            
            # Iterate downwards to Jan 1 roughly (SID 764000)
            # We don't need a hard stop if we check date in parse_story
            for sid in range(max_sid, 764000, -1):
                url = f"https://www.malaysiakini.com/_next/data/{self.build_id}/news/{sid}.json?lang=news&sid={sid}"
                yield scrapy.Request(url, callback=self.parse_story_json, meta={'sid': sid})
                
        except Exception as e:
            self.logger.error(f"Error starting SID crawl: {e}")

    def parse_story_json(self, response):
        sid = response.meta['sid']
        if response.status != 200:
            return

        try:
            data = json.loads(response.text)
            story = data.get('pageProps', {}).get('story', {})
        except Exception:
            return

        if not story or not story.get('title'):
            return

        # Filters: language and date
        if story.get('language') != 'en' and story.get('lang') != 'en':
            return
            
        pub_date_unix = story.get('date_pub')
        if not pub_date_unix:
            return

        dt = datetime.fromtimestamp(pub_date_unix)
        if dt < self.cutoff_date:
            self.logger.debug(f"SID {sid} date {dt} before cutoff {self.cutoff_date}")
            return

        title = story.get('title')
        content_html = story.get('content') or story.get('summary')
        author = story.get('author') or "Malaysiakini"
        
        # Content cleaning
        if content_html:
            soup = BeautifulSoup(content_html, 'html.parser')
            for s in soup(['script', 'style', 'iframe', 'ins', 'button', 'svg']):
                s.decompose()
            content_text = soup.get_text("\n\n").strip()
        else:
            content_text = ""

        article_url = f"https://www.malaysiakini.com/news/{sid}"

        item = NewsItem()
        item['title'] = title.strip()
        item['url'] = article_url
        item['publish_time'] = dt.strftime("%Y-%m-%d %H:%M:%S")
        item['author'] = str(author).strip()
        item['content'] = content_text
        item['section'] = story.get('category') or "news"
        item['language'] = "en"
        
        yield item
