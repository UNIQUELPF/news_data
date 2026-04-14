import scrapy
import json
from datetime import datetime
from news_scraper.spiders.base_spider import BaseNewsSpider

class IqElaphSpider(BaseNewsSpider):
    name = "iq_elaph"

    country_code = 'IRQ'

    country = '伊拉克'
    allowed_domains = ["elaph.com", "api.elaph.com"]
    
    api_url_tmpl = "https://api.elaph.com/v2/web/com/marticles/index/economics/{}"
    
    use_curl_cffi = True
    
    # 模拟最新版浏览器指纹头信息
    api_headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
        "Referer": "https://elaph.com/",
        "Origin": "https://elaph.com",
        "Sec-Ch-Ua": '"Chromium";v="146", "Not-A.Brand";v="24", "Google Chrome";v="146"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"macOS"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
    }
    
    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "news_scraper.middlewares.CurlCffiMiddleware": 543,
            "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
        },
        "CURLL_CFFI_IMPERSONATE": "chrome120",
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1
    }
    
    target_table = "iq_elaph_news"

    def start_requests(self):
        yield scrapy.Request(
            self.api_url_tmpl.format(1), 
            headers=self.api_headers,
            meta={'page': 1}
        )

    def parse(self, response):
        try:
            res_data = json.loads(response.text)
            articles = res_data.get('data', [])
            page = response.meta.get('page', 1)
            self.logger.info(f"Elaph API: Page {page} fetched {len(articles)} items with status {response.status}")
        except Exception as e:
            self.logger.error(f"JSON Parse Error: {e} at {response.url}")
            return

        if not articles:
            return

        valid_count = 0
        for art in articles:
            ts = art.get('RelativeTime', 0)
            if not ts: continue
            
            pub_date = datetime.fromtimestamp(int(ts))
            
            if not self.filter_date(pub_date):
                continue
                
            valid_count += 1
            rel_url = art.get('PostingURL')
            if rel_url:
                yield scrapy.Request(
                    f"https://elaph.com{rel_url}", 
                    callback=self.parse_article,
                    headers=self.api_headers,
                    meta={'pub_date': pub_date}
                )

        if valid_count > 0:
            next_page = page + 1
            yield scrapy.Request(
                self.api_url_tmpl.format(next_page),
                callback=self.parse,
                headers=self.api_headers,
                meta={'page': next_page}
            )

    def parse_article(self, response):
        title = response.css('h1.article-title::text').get("").strip()
        if not title:
            title = response.css('meta[property="og:title"]::attr(content)').get("").strip()
            
        body_parts = response.css('div.content-body p::text, div.content-body p *::text').getall()
        cleaned_content = "\n\n".join([p.strip() for p in body_parts if len(p.strip()) > 30])

        if cleaned_content:
            yield {
                "url": response.url,
                "title": title,
                "content": cleaned_content,
                "publish_time": response.meta.get('pub_date'),
                "author": "Elaph News",
                "language": "ar",
                "section": "Economics"
            }
