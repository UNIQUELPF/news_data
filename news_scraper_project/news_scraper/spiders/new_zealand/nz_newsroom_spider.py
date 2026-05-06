import scrapy
import json
from datetime import datetime
from news_scraper.spiders.smart_spider import SmartSpider


class NzNewsroomSpider(SmartSpider):
    name = "nz_newsroom"
    country_code = 'NZL'
    country = '新西兰'
    language = 'en'
    source_timezone = 'Pacific/Auckland'
    start_date = '2024-01-01'
    allowed_domains = ["newsroom.co.nz"]
    fallback_content_selector = '.entry-content'

    use_curl_cffi = True
    strict_date_required = False

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "news_scraper.middlewares.CurlCffiMiddleware": 543,
            "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
        },
        "CURLL_CFFI_IMPERSONATE": "chrome120",
        "CONCURRENT_REQUESTS": 4,
        "DOWNLOAD_DELAY": 1
    }

    async def start(self):
        yield scrapy.Request(
            "https://newsroom.co.nz/category/economy/",
            callback=self.parse,
            dont_filter=True,
        )

    def parse(self, response):
        if self._stop_pagination:
            return
        article_links = response.css('a[rel="bookmark"]::attr(href)').getall()

        has_valid_item_in_window = False
        for link in article_links:
            if self.should_process(link):
                has_valid_item_in_window = True
                yield response.follow(link, self.parse_article)

        if has_valid_item_in_window:
            next_page = response.css('a.next.page-numbers::attr(href)').get()
            if next_page:
                yield response.follow(next_page, self.parse)

    def parse_article(self, response):
        # Custom date extraction from LD-JSON
        pub_date = None
        ld_jsons = response.css('script[type="application/ld+json"]::text').getall()
        for raw in ld_jsons:
            try:
                data = json.loads(raw)
                graph = data.get('@graph', [data]) if isinstance(data, dict) else [data]
                for item in graph:
                    if isinstance(item, dict) and item.get('@type') in ['NewsArticle', 'Article', 'BlogPosting']:
                        date_str = item.get('datePublished')
                        if date_str:
                            pub_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                            pub_date = self.parse_to_utc(pub_date)
                            break
                if pub_date:
                    break
            except Exception:
                continue

        if not pub_date:
            date_meta = response.css('time.entry-date.published::attr(datetime)').get()
            if date_meta:
                try:
                    pub_date = datetime.fromisoformat(date_meta.replace('Z', '+00:00'))
                    pub_date = self.parse_to_utc(pub_date)
                except Exception:
                    pass

        item = self.auto_parse_item(response)
        item['publish_time'] = pub_date or item.get('publish_time')
        item['author'] = response.css('.author-name a::text').get("Newsroom")
        item['section'] = 'Economy'

        if not self.should_process(response.url, item.get('publish_time')):
            self._stop_pagination = True
            return

        if item.get('content_plain') and len(item['content_plain']) > 50:
            yield item
