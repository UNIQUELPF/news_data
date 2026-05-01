import scrapy
import re
import dateparser
from news_scraper.spiders.smart_spider import SmartSpider

class IndiaDigitSpider(SmartSpider):
    name = 'india_digit'
    country_code = 'IND'
    country = '印度'
    language = 'en'
    allowed_domains = ['digit.in']
    target_table = "ind_digit"
    
    source_timezone = 'Asia/Kolkata' # India is UTC+5:30
    use_curl_cffi = False
    
    fallback_content_selector = "article, .article_content, .entry-content, .post-content"

    custom_settings = {
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1,
        "AUTOTHROTTLE_ENABLED": True,
        "HTTPERROR_ALLOWED_CODES": [400],
    }

    # AJAX endpoint configuration
    ajax_url = "https://www.digit.in/wp-admin/admin-ajax.php"
    posts_per_page = 12

    def start_requests(self):
        # Step 1: Fetch the main news page to extract the security nonce (filternonce)
        yield scrapy.Request(
            "https://www.digit.in/news/", 
            callback=self.parse_start_page, 
            dont_filter=True
        )

    def parse_start_page(self, response):
        # Extract filternonce from the script variables in the page
        nonce_match = re.search(r'"filternonce":"([^"]+)"', response.text)
        if not nonce_match:
            self.logger.error("Could not find filternonce in start page. Aborting.")
            return

        self.filternonce = nonce_match.group(1)
        self.logger.info(f"Found filternonce: {self.filternonce}. Starting AJAX crawl.")

        # Start first AJAX request
        yield self.make_ajax_request(paged=1, offset=0)

    def make_ajax_request(self, paged, offset):
        """Constructs the POST request using standard urlencode."""
        from urllib.parse import urlencode
        
        params = [
            ('action', 're_filterpost'),
            ('filterargs[post_type][]', 'post'),
            ('filterargs[post_type][]', 'reviews'),
            ('filterargs[orderby]', 'post_date'),
            ('filterargs[order]', 'DESC'),
            ('filterargs[post_status]', 'publish'),
            ('filterargs[tax_query][0][taxonomy]', 'digitlang'),
            ('filterargs[tax_query][0][field]', 'slug'),
            ('filterargs[tax_query][0][terms]', 'en'),
            ('filterargs[tax_query][1][taxonomy]', 'contenttype'),
            ('filterargs[tax_query][1][field]', 'slug'),
            ('filterargs[tax_query][1][terms]', 'news'),
            ('filterargs[tax_query][relation]', 'AND'),
            ('filterargs[paged]', str(paged)),
            ('filterargs[posts_per_page]', str(self.posts_per_page)),
            ('template', 'query_type1'),
            ('containerid', 'rh_loop_221144211'),
            ('offset', str(offset)),
            ('innerargs[disable_btn]', '1'),
            ('innerargs[disable_act]', '0'),
            ('innerargs[price_meta]', '2'),
            ('innerargs[aff_link]', '0'),
            ('security', self.filternonce)
        ]
        
        body = urlencode(params)
        
        return scrapy.Request(
            self.ajax_url,
            method='POST',
            body=body,
            headers={
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'X-Requested-With': 'XMLHttpRequest',
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'Referer': 'https://www.digit.in/news/',
                'Origin': 'https://www.digit.in',
            },
            callback=self.parse_list,
            meta={'paged': paged, 'offset': offset},
            dont_filter=True
        )

    def parse_list(self, response):
        """Parses the AJAX HTML response containing news item blocks."""
        if response.status == 400:
            self.logger.error(f"AJAX request failed with 400. Response body: {response.text[:200]}")
            return
        items = response.css('.news-community')
        if not items:
            self.logger.info("No more items found in AJAX response.")
            return

        has_valid_item_in_window = False
        for item in items:
            url_node = item.css('h2 a::attr(href)').get()
            if not url_node:
                continue
                
            url = response.urljoin(url_node)
            
            # Date parsing from listing: e.g. "29-Apr-2026"
            date_text = item.css('.date_meta::text').get()
            publish_time = None
            if date_text:
                publish_time = self.parse_to_utc(dateparser.parse(date_text.strip()))

            if self.should_process(url, publish_time):
                has_valid_item_in_window = True
                yield scrapy.Request(
                    url, 
                    callback=self.parse_detail, 
                    meta={'publish_time_hint': publish_time}
                )

        # Pagination logic
        if has_valid_item_in_window:
            current_paged = response.meta.get('paged', 1)
            current_offset = response.meta.get('offset', 0)
            
            # Continue to next page if within window and safety limit
            if current_paged < 30: # Slightly increased page limit for AJAX
                next_paged = current_paged + 1
                next_offset = current_offset + self.posts_per_page
                yield self.make_ajax_request(paged=next_paged, offset=next_offset)


    def parse_detail(self, response):
        """Parses the detail page of a news article."""
        item = self.auto_parse_item(
            response,
            title_xpath="//h1/text() | //meta[@property='og:title']/@content",
            publish_time_xpath="//meta[@property='article:published_time']/@content | //meta[@name='publish-date']/@content"
        )
        
        # Priority for og:image as featured image
        og_image = response.xpath("//meta[@property='og:image']/@content").get()
        if og_image:
            if not item.get('images'):
                item['images'] = []
            if og_image not in item['images']:
                item['images'].insert(0, og_image)

        # Stop if older than cutoff (for incremental mode)
        if not self.full_scan and item['publish_time'] and item['publish_time'] < self.cutoff_date:
            return

        item['author'] = response.css('.author_detail_box a::text, .post-author a::text, [rel="author"]::text').get() or "Digit Staff"
        item['country_code'] = self.country_code
        item['country'] = self.country
        
        yield item
