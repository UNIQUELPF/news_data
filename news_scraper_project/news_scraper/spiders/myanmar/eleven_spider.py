import scrapy
from news_scraper.spiders.smart_spider import SmartSpider


class MyanmarElevenSpider(SmartSpider):
    name = 'mm_eleven'
    country_code = 'MMR'
    country = '缅甸'
    language = 'en'
    source_timezone = 'Asia/Yangon'
    allowed_domains = ['news-eleven.com']
    start_urls = ['https://news-eleven.com/business']
    fallback_content_selector = '.field-name-body'
    strict_date_required = False
    MAX_PAGES = 100
    dateparser_settings = {"DATE_ORDER": "DMY"}

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.0,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 4,
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        }
    }

    async def start(self):
        yield scrapy.Request(
            f"{self.start_urls[0]}?page=0",
            callback=self.parse_list,
            meta={'page': 0},
        dont_filter=True,
        )

    def parse_list(self, response):
        articles = response.css('.frontpage-title a::attr(href)').getall()
        if not articles:
            articles = response.css('.news-top-featured-large-category a::attr(href)').getall()

        # Filter and deduplicate links we want to process
        urls_to_process = []
        for link in articles:
            full_url = response.urljoin(link)
            if '/article/' not in full_url:
                continue
            if self.should_process(full_url):
                urls_to_process.append(full_url)

        current_page = response.meta.get('page', 0)

        if urls_to_process:
            # Start sequential detail fetching
            next_url = urls_to_process.pop(0)
            yield scrapy.Request(
                next_url,
                callback=self.parse_article_sync,
                meta={
                    'urls_to_process': urls_to_process,
                    'any_item_new': False,
                    'page': current_page
                }
            )
        else:
            self.logger.info(f"No new/valid URLs on page {current_page}. Stopping pagination.")

    def parse_article_sync(self, response):
        item = self.auto_parse_item(
            response,
            title_xpath="//h1[@class='article-title']/text()",
            publish_time_xpath="//span[@class='date-display-single']/text()",
        )
        item['author'] = 'Eleven Media Group'
        item['section'] = 'Business'
        
        title = item.get('title', '')
        if title and any('က' <= char <= '႟' for char in title):
            item['language'] = 'my'

        # Check if the extracted publish date is valid and within the window
        pub_time = item.get('publish_time')
        is_new = False
        if pub_time:
            is_new = self.should_process(response.url, pub_time)
        else:
            is_new = not self.strict_date_required

        if is_new:
            response.meta['any_item_new'] = True
            if item.get('content_plain') and len(item['content_plain']) > 100:
                yield item

        # Process the remaining URLs for this list page
        urls_to_process = response.meta.get('urls_to_process', [])
        current_page = response.meta.get('page', 0)
        any_item_new = response.meta.get('any_item_new', False)

        if urls_to_process:
            next_url = urls_to_process.pop(0)
            yield scrapy.Request(
                next_url,
                callback=self.parse_article_sync,
                meta={
                    'urls_to_process': urls_to_process,
                    'any_item_new': any_item_new,
                    'page': current_page
                }
            )
        else:
            # All URLs for this list page are processed! Now decide if we should load the next page
            if any_item_new and current_page < self.MAX_PAGES:
                next_page = current_page + 1
                next_url = f"{self.start_urls[0]}?page={next_page}"
                self.logger.info(f"Page {current_page} had new articles. Proceeding to page {next_page}: {next_url}")
                yield scrapy.Request(
                    next_url,
                    callback=self.parse_list,
                    meta={'page': next_page},
                    dont_filter=True
                )
            else:
                self.logger.info(f"All articles on page {current_page} were old or already scraped. Stopping pagination.")
