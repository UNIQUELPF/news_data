import scrapy
from news_scraper.spiders.smart_spider import SmartSpider
from email.utils import parsedate_to_datetime


class MexicoInfobaeSpider(SmartSpider):
    name = 'mexico_infobae'
    country_code = 'MEX'
    country = '墨西哥'
    language = 'es'
    source_timezone = 'America/Mexico_City'
    allowed_domains = ['infobae.com']
    start_urls = ['https://www.infobae.com/arc/outboundfeeds/rss/category/mexico/']
    fallback_content_selector = '.article-body'
    strict_date_required = True
    dateparser_settings = {"DATE_ORDER": "DMY"}

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 0.8,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 8,
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        }
    }

    async def start(self):
        for url in self.start_urls:
            yield scrapy.Request(
                url,
                callback=self.parse_feed,
                dont_filter=True,
            )

    def parse_feed(self, response):
        for item in response.xpath("//channel/item"):
            url = item.xpath("./link/text()").get()
            if not url:
                continue
            if '/mexico/' not in url:
                continue

            publish_time = self._parse_rss_datetime(item.xpath("./pubDate/text()").get())
            if not self.should_process(url, publish_time):
                continue

            meta = {
                'rss_title': item.xpath("./title/text()").get(),
                'publish_time_hint': publish_time,
            }
            yield scrapy.Request(url, callback=self.parse_article, meta=meta)

    def parse_article(self, response):
        item = self.auto_parse_item(
            response,
            title_xpath="//h1/text()",
            publish_time_xpath="//meta[@property='article:published_time']/@content",
        )
        if not item.get("title") or not item.get("content_plain"):
            item["title"] = item.get("title") or response.meta.get("rss_title")
            if not item.get("publish_time"):
                item["publish_time"] = response.meta.get("publish_time_hint")

        # Final safety check on publish_time (V2 requirement)
        if item.get('publish_time') and not self.should_process(response.url, item['publish_time']):
            self._stop_pagination = True
            return

        item['author'] = response.css('.author-name::text').get() or 'Infobae Mexico'
        item['section'] = 'Ultimas Noticias'

        if item.get('content_plain') and len(item['content_plain']) > 200:
            yield item

    def _parse_rss_datetime(self, value):
        if not value:
            return None
        try:
            return parsedate_to_datetime(value).replace(tzinfo=None)
        except Exception:
            return None
