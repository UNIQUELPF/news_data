import scrapy
import dateparser
from news_scraper.spiders.smart_spider import SmartSpider

class AlbaniaBankSpider(SmartSpider):
    """
    Modernized Bank of Albania Spider.
    """
    name = 'albania_bank'
    source_timezone = 'Europe/Tirane'
    
    country_code = 'ALB'
    country = '阿尔巴尼亚'
    
    allowed_domains = ['bankofalbania.org']
    
    custom_settings = {
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 1,
    }

    use_curl_cffi = True

    async def start(self):
        for url in ['https://www.bankofalbania.org/Shtypi/Njoftimet_per_shtyp/']:
            yield scrapy.Request(url, callback=self.parse, dont_filter=True)
    
    fallback_content_selector = "div.fc, article, .content"

    def parse(self, response):
        """Parses the press release list page."""
        rows = response.css('div.row')
        self.logger.info(f"Checking {len(rows)} potential rows on {response.url}")

        has_valid_item_in_window = False
        
        for row in rows:
            date_str = row.css('.text-dark.pb-1::text').get()
            title_node = row.css('h5 a.text-dark.font-weight-bold')
            
            if not date_str or not title_node:
                continue
                
            url = response.urljoin(title_node.attrib.get('href'))
            
            # Parse date for early stopping
            dt_local = dateparser.parse(date_str, languages=['sq', 'en'])
            publish_time = self.parse_to_utc(dt_local)
            
            if not self.should_process(url, publish_time):
                continue
                
            has_valid_item_in_window = True
            yield scrapy.Request(
                url,
                callback=self.parse_detail,
                dont_filter=self.full_scan,
                meta={'publish_time_hint': publish_time}
            )

        # Pagination logic
        if has_valid_item_in_window:
            next_page = response.css('a.page-link[title="Faqja pasardhëse"]::attr(href)').get() \
                        or response.xpath('//a[contains(@class, "page-link") and contains(@title, "pasardhëse")]/@href').get()
            if next_page:
                yield response.follow(next_page, callback=self.parse, dont_filter=True)

    def parse_detail(self, response):
        """Standardized detail parsing."""
        yield self.auto_parse_item(response)

