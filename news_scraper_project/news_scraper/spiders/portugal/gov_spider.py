import scrapy
import json
from dateutil import parser as dateutil_parser
from news_scraper.spiders.smart_spider import SmartSpider


class PortugalGovSpider(SmartSpider):
    name = 'pt_gov'
    country_code = 'PRT'
    country = '葡萄牙'
    language = 'pt'
    source_timezone = 'Europe/Lisbon'
    allowed_domains = ['portugal.gov.pt']
    fallback_content_selector = 'div#regText.gov-texts'
    start_urls = ['https://www.portugal.gov.pt/pt/gc25/comunicacao/noticias']

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.5,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 1,
        'DOWNLOAD_HANDLERS': {
            'http': 'scrapy.core.downloader.handlers.http11.HTTP11DownloadHandler',
            'https': 'scrapy.core.downloader.handlers.http11.HTTP11DownloadHandler',
        },
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        }
    }

    async def start(self):
        # 葡萄牙政府站翻页通常支持 p 参数
        # Yield only page 1; circuit breaker in parse_list drives subsequent pages
        url = f"{self.start_urls[0]}?p=1"
        yield scrapy.Request(url, callback=self.parse_list, meta={'page': 1}, dont_filter=True)

    def parse_list(self, response):
        self.logger.info(f"Received response from {response.url} with length {len(response.text)}")
        # 更加宽松的链接提取逻辑
        articles = response.xpath(
            '//a[contains(@href, "/comunicacao/noticia")]/@href | '
            '//a[contains(@href, "/comunicacao/noticias/")]/@href | '
            '//a[contains(@href, "noticia")]/@href'
        ).getall()
        if not articles:
            articles = self._extract_next_data_links(response)
        self.logger.info(f"Discovered {len(articles)} potential articles on {response.url}")

        has_valid_item_in_window = False

        for link in articles:
            full_url = response.urljoin(link)
            # URL-based dedup and circuit breaker
            if not self.should_process(full_url):
                continue
            has_valid_item_in_window = True
            yield scrapy.Request(full_url, callback=self.parse_article)

        # Circuit breaker: yield next page only if valid items found and not stopped
        if has_valid_item_in_window and not self._stop_pagination:
            page = response.meta.get('page', 1) + 1
            next_url = f"{self.start_urls[0]}?p={page}"
            yield scrapy.Request(next_url, callback=self.parse_list, meta={'page': page}, dont_filter=True)

    def _extract_next_data_links(self, response):
        raw = response.css('script#__NEXT_DATA__::text').get()
        if not raw:
            return []
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return []

        links = []

        def walk(value):
            if isinstance(value, dict):
                for key in ('url', 'href', 'path'):
                    candidate = value.get(key)
                    if isinstance(candidate, str) and '/comunicacao/noticia' in candidate:
                        if candidate.rstrip('/').split('?')[0].endswith('/comunicacao/noticias'):
                            continue
                        links.append(candidate)
                for child in value.values():
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)

        walk(data)
        return list(dict.fromkeys(links))

    def parse_article(self, response):
        item = self.auto_parse_item(
            response,
            title_xpath="//h1/text()",
        )
        self.logger.info(f"Parsing article: {item.get('title')} at {response.url}")

        # 自定义日期解析：政府站的日期格式为 "dd/mm/yyyy às HHhMM"
        pub_time_raw = response.css('div.time::text').get()
        if pub_time_raw:
            self.logger.info(f"Found date raw: {pub_time_raw}")
            try:
                clean_date = pub_time_raw.replace('às', '').replace('h', ':').strip()
                pub_time = dateutil_parser.parse(clean_date)
                item['publish_time'] = self.parse_to_utc(pub_time)
            except Exception as e:
                self.logger.warning(f"Date parse failed for {pub_time_raw}: {e}")

        if not item.get('publish_time'):
            return

        # Date-based circuit breaker: stop pagination when article is too old
        if not self.should_process(response.url, item.get('publish_time')):
            self._stop_pagination = True
            return

        item['author'] = 'Governo da República Portuguesa'
        item['section'] = 'Comunicado Oficial'

        if item.get('content_plain') and len(item['content_plain']) > 50:
            self.logger.info(f"Scraped article: {item.get('title')} - {response.url}")
            yield item
