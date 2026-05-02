import scrapy
import jdatetime
import re
from datetime import datetime
from news_scraper.spiders.smart_spider import SmartSpider

class IranDonyaSpider(SmartSpider):
    name = 'iran_donya'
    source_timezone = 'Asia/Tehran'
    fallback_content_selector = ".news-text"
    country_code = 'IRN'
    country = '伊朗'
    language = 'fa'
    
    allowed_domains = ['donya-e-eqtesad.com']
    
    custom_settings = {
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "AUTOTHROTTLE_ENABLED": True,
    }

    use_curl_cffi = True
    
    # Persian digits translation table
    PERSIAN_DIGITS = str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789')

    async def start(self):
        urls = [
            "https://donya-e-eqtesad.com/%D8%A8%D8%AE%D8%B4-%D8%A7%D9%82%D8%AA%D8%B5%D8%A7%D8%AF-183"
        ]
        for url in urls:
            yield scrapy.Request(url=url, callback=self.parse, dont_filter=True)

    def parse(self, response):
        # Extract article items which contain both link and date
        items = response.css('li[data-date]')
        
        self.logger.info(f"Found {len(items)} items on {response.url}")

        has_valid_item_in_window = False
        for item in items:
            link = item.css('h2.title a::attr(href)').get() or item.css('a::attr(href)').get()
            if not link:
                continue
            
            url = response.urljoin(link)
            
            # Extract date from data-date attribute
            raw_date = item.attrib.get('data-date')
            publish_time = self.parse_date(raw_date) if raw_date else None
            
            if not self.should_process(url, publish_time):
                # If we hit an item out of window, and items are sorted (usually they are),
                # we can stop processing this page and prevent further pagination.
                if publish_time and publish_time < self.cutoff_date:
                    self.logger.info(f"Hit date boundary at {publish_time}. Stopping pagination.")
                    has_valid_item_in_window = False
                    break
                continue
            
            has_valid_item_in_window = True 
            yield scrapy.Request(
                url=url, 
                callback=self.parse_detail,
                dont_filter=self.full_scan,
                meta={'publish_time_hint': publish_time}
            )

        if has_valid_item_in_window:
            # Pagination logic
            next_pages = response.css('footer.service_pagination a::attr(href)').getall()
            # The original logic used a page number comparison. 
            # Standard way is to just find the "Next" link or increment page param.
            # Let's try to find a "Next" button specifically if possible, or just the next page URL.
            current_page_num = self._get_page_num(response.url)
            for p_link in next_pages:
                p_url = response.urljoin(p_link)
                p_num = self._get_page_num(p_url)
                if p_num > current_page_num:
                    yield scrapy.Request(url=p_url, callback=self.parse, dont_filter=True)
                    break

    def _get_page_num(self, url):
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        try:
            return int(params.get('page', [1])[0])
        except:
            return 1

    def parse_detail(self, response):
        # Extract date first for should_process
        # Machine-readable time tag is preferred
        publish_time_str = response.xpath("//time[@itemprop='datepublished']/@datetime").get()
        publish_time = None
        if publish_time_str:
            publish_time = self.parse_date(publish_time_str)
        
        if not publish_time:
            # Fallback to Persian date in text
            header_date_match = response.xpath('//*[contains(text(), "۱۴۰")]/text()').re(r'\d{4}/\d{2}/\d{2}')
            if header_date_match:
                date_str = header_date_match[0]
                publish_time = self._parse_persian_date(date_str)
                if publish_time:
                    publish_time = self.parse_to_utc(publish_time)

        # Fallback to meta tags
        if not publish_time:
            meta_date = response.css('meta[property="article:published_time"]::attr(content)').get()
            if meta_date:
                publish_time = self.parse_to_utc(meta_date)

        if not self.should_process(response.url, publish_time):
            return

        # Use auto_parse_item but provide some hints or overrides if needed
        item = self.auto_parse_item(
            response,
            publish_time_xpath="//time[@itemprop='datepublished']/@datetime",
            title_xpath="//h1/text()",
        )
        
        # Override publish_time if we found it manually
        if publish_time:
            item['publish_time'] = publish_time
            
        # Ensure og:image is prioritized
        og_image = response.xpath("//meta[@property='og:image']/@content").get()
        if og_image:
            if 'images' not in item or not item['images']:
                item['images'] = [og_image]
            elif og_image not in item['images']:
                item['images'].insert(0, og_image)

        # Clean up images list to be pure strings
        if 'images' in item and item['images']:
            item['images'] = [img if isinstance(img, str) else img.get('url') for img in item['images'] if img]

        item['author'] = 'Donya-e-Eqtesad'
        item['section'] = 'Economy'
        
        yield item

    def _parse_persian_date(self, date_str):
        try:
            date_str = date_str.translate(self.PERSIAN_DIGITS)
            parts = [int(p) for p in date_str.split('/') if p.strip()]
            if len(parts) != 3:
                return None
            
            sh_year, sh_month, sh_day = parts
            jd = jdatetime.date(sh_year, sh_month, sh_day)
            gregorian_date = jd.togregorian()
            return datetime.combine(gregorian_date, datetime.min.time())
        except Exception as e:
            self.logger.error(f"Error parsing date {date_str}: {e}")
            return None
