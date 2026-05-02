import scrapy
from news_scraper.spiders.smart_spider import SmartSpider

class AfricaThePresidencySpider(SmartSpider):
    """
    South Africa Presidency spider.
    Modernized V2: Captures official speeches, statements, and advisories using standard V2 patterns.
    """
    name = 'africa_thepresidency'
    country_code = 'ZAF'
    country = '南非'
    language = 'en'
    source_timezone = 'Africa/Johannesburg'
    use_curl_cffi = True
    fallback_content_selector = ".node-content, .field-items"
    allowed_domains = ['thepresidency.gov.za']

    custom_settings = {
        'DOWNLOAD_DELAY': 1,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 2,
        'RANDOMIZE_DOWNLOAD_DELAY': True,
        'DOWNLOADER_MIDDLEWARES': {
            'news_scraper.middlewares.CurlCffiMiddleware': 500,
        }
    }

    def start_requests(self):
        url = "https://www.thepresidency.gov.za/speeches-statements-advisories?page=0"
        yield scrapy.Request(url, callback=self.parse_list, meta={'page': 0})

    def parse_list(self, response):
        articles = response.css('.ssa-grid-view-row, div.views-row, article, li.views-row')
        if not articles:
            self.logger.info(f"No articles found on {response.url}. Stopping.")
            return

        has_valid_item_in_window = False
        for article in articles:
            a_elem = article.css('a')
            if not a_elem:
                continue
                
            url = a_elem.attrib.get('href') or a_elem.css('::attr(href)').get()
            if url and url.startswith('/'):
                url = "https://www.thepresidency.gov.za" + url
            
            if not url:
                continue

            # Date extraction from list page
            date_str = article.css('time::attr(datetime)').get()
            if not date_str:
                date_el = article.css('.views-field-created .field-content::text, .date::text')
                if date_el:
                    date_str = " ".join([d.strip() for d in date_el.getall() if d.strip()])
            
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
            next_url = f"https://www.thepresidency.gov.za/speeches-statements-advisories?page={next_page}"
            yield scrapy.Request(next_url, callback=self.parse_list, meta={'page': next_page})

    def parse_detail(self, response):
        # Automated extraction using SmartSpider V2
        item = self.auto_parse_item(
            response,
            title_xpath="//h1//text()",
            publish_time_xpath="//time/@datetime"
        )
        
        # Ensure main image is captured
        main_image = response.css(".field-items img::attr(src), .node-content img::attr(src)").get() or \
                     response.xpath("//meta[@property='og:image']/@content").get()
        if main_image:
            main_image = response.urljoin(main_image)
            images = item.get('images') or []
            if main_image not in images:
                images.insert(0, main_image)
                item['images'] = images
        
        # Presidency articles usually don't have a single author meta tag
        if not item.get('author'):
            item['author'] = "The Presidency"
            
        yield item
