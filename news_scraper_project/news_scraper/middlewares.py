from scrapy import signals
import time

class BatchDelayMiddleware:
    def __init__(self, crawler):
        self.crawler = crawler
        self.counter = 0
        self.batch_size = crawler.settings.getint('BATCH_SIZE', 2000)
        self.delay = crawler.settings.getint('BATCH_DELAY', 10)

        crawler.signals.connect(self.item_scraped, signal=signals.item_scraped)

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler)

    def item_scraped(self, item, response, spider):
        self.counter += 1
        if self.counter % self.batch_size == 0:
            spider.logger.info(f"*** Batch Limit Reached ({self.counter} items). Pausing for {self.delay} seconds... ***")
            time.sleep(self.delay)
            spider.logger.info("*** Resuming crawl... ***")

    def process_request(self, request, spider):
        return None

from scrapy.http import HtmlResponse

class CurlCffiMiddleware:
    def process_request(self, request, spider):
        # Skip requests marked for Playwright
        if request.meta.get('playwright'):
            return None
            
        if getattr(spider, 'use_curl_cffi', False):
            from curl_cffi import requests as curl_requests
            try:
                spider.logger.debug(f"Intercepting {request.url} via curl_cffi")
                headers = {k.decode('utf-8'): v[0].decode('utf-8') for k, v in request.headers.items()}
                response = curl_requests.get(request.url, impersonate='chrome120', timeout=30, headers=headers)
                return HtmlResponse(
                    url=request.url,
                    status=response.status_code,
                    body=response.content,
                    encoding='utf-8',
                    request=request
                )
            except Exception as e:
                spider.logger.error(f"CurlCffi error on {request.url}: {e}")
        return None
