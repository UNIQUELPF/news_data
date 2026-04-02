import scrapy
from datetime import datetime
import json
from news_scraper.spiders.base_spider import BaseNewsSpider

class SgMasSpider(BaseNewsSpider):
    name = "sg_mas"
    allowed_domains = ["mas.gov.sg"]
    
    api_url = "https://www.mas.gov.sg/api/v1/search?q=*:*&fq=mas_mastercontenttypes_sm:%22News%22&sort=mas_date_tdt%20desc&start={}&rows=20&json.nl=map"
    
    use_curl_cffi = True
    
    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "news_scraper.middlewares.CurlCffiMiddleware": 543,
            "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
        },
        "CURLL_CFFI_IMPERSONATE": "chrome120",
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1
    }
    
    target_table = "sg_mas_news"

    def start_requests(self):
        yield scrapy.Request(self.api_url.format(0), meta={"start": 0})

    def parse(self, response):
        try:
            data = json.loads(response.text)
            docs = data.get("response", {}).get("docs", [])
            start_val = response.meta.get("start", 0)
            self.logger.info(f"MAS API: Found {len(docs)} docs at start={start_val}")
        except Exception as e:
            self.logger.error(f"Failed to parse MAS API: {e}")
            return

        if not docs:
            return

        valid_items_in_page = 0
        for doc in docs:
            path = doc.get("page_url_s")
            date_str = doc.get("mas_date_tdt")
            
            if not path or not date_str:
                continue
            
            try:
                pub_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except Exception:
                continue

            if self.filter_date(pub_date):
                valid_items_in_page += 1
                yield response.follow(
                    path, 
                    self.parse_article,
                    meta={"pub_date": pub_date}
                )

        # 只要当前页有 2026/01/01 的文章，就继续翻页
        if valid_items_in_page > 0:
            next_start = response.meta.get("start", 0) + 20
            yield scrapy.Request(
                self.api_url.format(next_start),
                callback=self.parse,
                meta={"start": next_start},
                dont_filter=True
            )

    def parse_article(self, response):
        title = response.css("h1.mas-text-h1::text").get("").strip()
        if not title:
            title = response.css("meta[property=\"og:title\"]::attr(content)").get("").strip()
        
        content_parts = response.css(".mas-rte-content p::text, .mas-rte-content li::text, .mas-rte-content table::text").getall()
        cleaned_content = "\n\n".join([p.strip() for p in content_parts if len(p.strip()) > 10])

        if not cleaned_content:
            content_parts = response.css("main p::text").getall()
            cleaned_content = "\n\n".join([p.strip() for p in content_parts if len(p.strip()) > 10])

        if cleaned_content:
            yield {
                "url": response.url,
                "title": title,
                "content": cleaned_content,
                "publish_time": response.meta.get("pub_date"),
                "author": "Monetary Authority of Singapore (MAS)",
                "language": "en",
                "section": response.url.split("/")[4] if len(response.url.split("/")) > 4 else "Finance"
            }
