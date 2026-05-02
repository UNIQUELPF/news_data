import scrapy
from news_scraper.spiders.smart_spider import SmartSpider

class AfricaTechCentralSpider(SmartSpider):
    """
    South Africa TechCentral spider.
    Modernized V2: Standard WordPress-style list/detail spider.
    """
    name = 'africa_techcentral'
    country_code = 'ZAF'
    country = '南非'
    language = 'en'
    source_timezone = 'Africa/Johannesburg'
    use_curl_cffi = True
    fallback_content_selector = ".entry-content, .post-content"
    allowed_domains = ['techcentral.co.za']

    custom_settings = {
        'DOWNLOAD_DELAY': 0.5,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 4,
        'RANDOMIZE_DOWNLOAD_DELAY': True,
        'DOWNLOADER_MIDDLEWARES': {
            'news_scraper.middlewares.CurlCffiMiddleware': 500,
        }
    }

    def start_requests(self):
        url = "https://techcentral.co.za/category/news/page/1/"
        yield scrapy.Request(url, callback=self.parse_list, meta={'page': 1})

    def parse_list(self, response):
        articles = response.css('article')
        if not articles:
            self.logger.info(f"No articles found on {response.url}. Stopping.")
            return

        has_valid_item_in_window = False
        for article in articles:
            # link
            title_node = article.css('h2.is-title a, h3.title a, a.image-link')
            url = title_node.css('::attr(href)').get()
            if not url:
                continue

            # datetime
            date_str = article.css('time::attr(datetime)').get()
            publish_time = self.parse_date(date_str)
            
            if self.should_process(url, publish_time):
                has_valid_item_in_window = True
                yield scrapy.Request(
                    url,
                    callback=self.parse_detail,
                    meta={'publish_time_hint': publish_time}
                )
            elif publish_time and publish_time < self.cutoff_date:
                self.logger.info(f"Hit date boundary at {publish_time}. Stopping pagination.")
                has_valid_item_in_window = False
                break

        if has_valid_item_in_window:
            next_page = response.meta['page'] + 1
            next_url = f"https://techcentral.co.za/category/news/page/{next_page}/"
            yield scrapy.Request(next_url, callback=self.parse_list, meta={'page': next_page})

    def parse_detail(self, response):
        # Automated extraction using SmartSpider V2
        item = self.auto_parse_item(
            response,
            title_xpath="//h1//text()",
            publish_time_xpath="//time/@datetime"
        )
        
        # Ensure main image is captured (trafilatura sometimes misses the lead image in WP)
        main_image = response.css(".entry-content img::attr(src), .post-content img::attr(src)").get() or \
                     response.xpath("//meta[@property='og:image']/@content").get()
        if main_image:
            main_image = response.urljoin(main_image)
            images = item.get('images') or []
            if main_image not in images:
                images.insert(0, main_image)
                item['images'] = images
        
        yield item
