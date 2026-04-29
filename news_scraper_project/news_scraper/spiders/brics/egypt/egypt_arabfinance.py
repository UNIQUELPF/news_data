import scrapy
import re
from datetime import datetime
from news_scraper.spiders.smart_spider import SmartSpider

class EgyptArabfinanceSpider(SmartSpider):
    name = 'egypt_arabfinance'
    country_code = 'EGY'
    country = '埃及'
    allowed_domains = ['arabfinance.com']
    target_table = 'egy_arabfinance'

    # SmartSpider Settings
    use_curl_cffi = True
    language = 'en'
    source_timezone = 'Africa/Cairo'
    fallback_content_selector = ".details, .news-details, .news-content, .article-content"

    def start_requests(self):
        url = "https://www.arabfinance.com/en/news/newssinglecategory/2"
        yield scrapy.Request(url, callback=self.parse_list, dont_filter=True, meta={'page': 1})

    def _parse_listing_date(self, date_text):
        if not date_text:
            return None
        date_text = date_text.replace("Updated", "").strip()
        
        # Handle relative time like 15h55m
        match = re.match(r'(\d+)h(\d+)m', date_text)
        if match:
            from datetime import timedelta
            return datetime.now() - timedelta(hours=int(match.group(1)), minutes=int(match.group(2)))
        
        # Handle relative days like 1d
        match = re.match(r'(\d+)d', date_text)
        if match:
            from datetime import timedelta
            return datetime.now() - timedelta(days=int(match.group(1)))

        # Fallback to dateparser for absolute dates like 4/28/2026
        import dateparser
        parsed = dateparser.parse(date_text, settings={'TIMEZONE': 'UTC', 'RETURN_AS_TIMEZONE_AWARE': False})
        return parsed

    def parse_list(self, response):
        cards = response.css('.news-thumb').xpath('..')
        if not cards:
            self.logger.warning(f"No cards found via .news-thumb on {response.url}")
            # Fallback to links only
            cards = response.css('a[href*="/en/news/newdetails/"]')
        
        self.logger.info(f"Found {len(cards)} potential articles on {response.url}")

        has_valid_item_in_window = False
        
        for card in cards:
            link_el = card.css('a[href*="/en/news/newdetails/"]::attr(href)').get()
            if not link_el:
                continue
                
            url = response.urljoin(link_el)
            
            # Try to extract date from the card
            date_text = card.css('.news-list-date::text').get()
            if not date_text:
                # try inner text if just ::text missed it due to <i> tag
                date_text = "".join(card.css('.news-list-date *::text').getall()).strip()
            
            publish_time = self._parse_listing_date(date_text)
            publish_time_utc = self.parse_to_utc(publish_time) if publish_time else None

            if self.should_process(url, publish_time_utc):
                has_valid_item_in_window = True
                meta_dict = {'publish_time_hint': publish_time_utc}
                if getattr(self, 'playwright', False):
                    meta_dict['playwright'] = True
                yield scrapy.Request(url, callback=self.parse_detail, meta=meta_dict)
            else:
                self.logger.debug(f"Skipping article {url} (date: {publish_time_utc})")

        if not has_valid_item_in_window:
            self.logger.info(f"No valid/new articles in current window on {response.url}. Panic break triggered.")

        if has_valid_item_in_window:
            page = response.meta.get('page', 1)
            
            pagination_spans = response.css('.pagination-results .pagination-number::text').getall()
            max_page = 100 # default fallback
            if pagination_spans and len(pagination_spans) >= 2:
                try:
                    max_page = int(pagination_spans[-1].strip())
                except ValueError:
                    pass
                    
            if page < max_page:
                next_page = page + 1
                next_url = f"https://www.arabfinance.com/en/news/newssinglecategory/2?page={next_page}"
                yield scrapy.Request(next_url, callback=self.parse_list, dont_filter=True, meta={'page': next_page})

    def parse_detail(self, response):
        # We need a custom extraction for title and publish_time because the structure is messy
        title = response.css('h1::text, h2.title::text').get()
        if title:
            title = title.strip()
            
        date_text = None
        for el in response.xpath('//*[contains(text(), "Updated ")]'):
            text = el.xpath('normalize-space(.)').get()
            if text and "Updated" in text and "202" in text:
                date_text = text
                break
                
        if not date_text:
            date_el = response.css('time, .date, .posted-on').getall()
            for d in date_el:
                if '202' in d:
                    date_text = d
                    break

        publish_time = None
        if date_text:
            clean_date_str = date_text.replace("Updated", "").strip()
            import dateparser
            parsed_date = dateparser.parse(clean_date_str, settings={'TIMEZONE': 'UTC'})
            if parsed_date:
                publish_time = parsed_date.replace(tzinfo=None)

        item = self.auto_parse_item(
            response,
            title_xpath=None,  # Handled above
            publish_time_xpath=None # Handled above
        )
        if not item:
            return

        if title:
            item['title'] = title
            
        if publish_time:
            item['publish_time'] = self.parse_to_utc(publish_time)
            
        # Stop processing if older than cutoff (unless full_scan is enabled)
        if not self.full_scan and item['publish_time'] and item['publish_time'] < self.cutoff_date:
            return

        featured_image = response.xpath("//meta[@property='og:image']/@content").get()
        if featured_image:
            current_images = item.get('images') or []
            if featured_image not in current_images:
                item['images'] = [featured_image] + current_images
            elif current_images[0] != featured_image:
                current_images.remove(featured_image)
                item['images'] = [featured_image] + current_images

        item['author'] = item.get('author') or "ArabFinance"

        yield item
