import scrapy
import re
from news_scraper.spiders.smart_spider import SmartSpider


class PlGovSpider(SmartSpider):
    name = "pl_gov"
    country_code = 'POL'
    country = '波兰'
    language = 'pl'
    source_timezone = 'Europe/Warsaw'
    start_date = '2024-01-01'
    allowed_domains = ["www.gov.pl"]
    fallback_content_selector = '.editor-content'

    use_curl_cffi = True
    strict_date_required = False

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

    def start_requests(self):
        yield scrapy.Request(
            "https://www.gov.pl/web/premier/wydarzenia?page=1",
            callback=self.parse
        )

    def parse(self, response):
        links = response.css('div.art-prev ul li .title a::attr(href)').getall()
        if not links:
            links = response.css('a[href*="/web/premier/"]::attr(href)').getall()

        has_valid_item_in_window = False
        for link in links:
            if not link.startswith('http'):
                link = "https://www.gov.pl" + link

            if '/web/premier/wydarzenia' in link or '/web/' not in link or '?page' in link:
                continue

            if self.should_process(link):
                has_valid_item_in_window = True
                yield scrapy.Request(
                    link,
                    callback=self.parse_article,
                    meta={"playwright": True}
                )

        if has_valid_item_in_window:
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
        # Custom date extraction (DD.MM.YYYY)
        date_str = response.css('p.event-date::text, .date::text, .article-header .date::text').get()
        if not date_str:
            raw_text = response.text
            match = re.search(r'(\d{2}\.\d{2}\.\d{4})', raw_text)
            if match:
                date_str = match.group(1)

        pub_date = None
        if date_str:
            pub_date = self.parse_date(date_str.strip())

        item = self.auto_parse_item(response)
        item['publish_time'] = pub_date or item.get('publish_time')
        item['author'] = 'Kancelaria Prezesa Rady Ministrów (KPRM)'
        item['section'] = 'Government Announcements'

        if not self.should_process(response.url, item.get('publish_time')):
            return

        if item.get('content_plain') and len(item['content_plain']) > 50:
            yield item
