import scrapy
import dateparser
import re
from news_scraper.spiders.smart_spider import SmartSpider

class AlbaniaMonitorSpider(SmartSpider):
    """
    Modernized Albania Monitor Spider.
    Inherits from SmartSpider for automated state and content handling.
    """
    name = 'albania_monitor'
    source_timezone = 'Europe/Tirane'
    
    country_code = 'ALB'
    country = '阿尔巴尼亚'
    
    allowed_domains = ['monitor.al']
    custom_settings = {
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 1,
    }

    use_curl_cffi = True

    async def start(self):
        for url in ['https://monitor.al/ekonomi/']:
            yield scrapy.Request(url, callback=self.parse, dont_filter=True)
    
    # CSS selector for the main content area
    fallback_content_selector = ".standard-content, .jeg_main_content, article"

    def _parse_card_date(self, card_root):
        date_str = card_root.css('.jeg_meta_date::text, .jeg_post_meta .jeg_meta_date::text, .jeg_post_date::text').get()
        if not date_str:
            text = " ".join(card_root.xpath(".//text()").getall())
            text = re.sub(r"\s+", " ", text).strip()
            match = re.search(
                r"(\d+\s+(?:day|days|week|weeks|dit[eë]|jav[eë])\s+m[eë]\s+par[eë]|[A-Za-z]+\s+\d{1,2},\s+\d{4})",
                text,
                flags=re.IGNORECASE,
            )
            date_str = match.group(1) if match else None

        if not date_str:
            return None

        normalized = (
            date_str.replace("më parë", "ago")
            .replace("me pare", "ago")
            .replace("ditë", "days")
            .replace("dite", "days")
            .replace("javë", "weeks")
            .replace("jave", "weeks")
        )
        dt_local = dateparser.parse(normalized, languages=['sq', 'en'])
        return self.parse_to_utc(dt_local) if dt_local else None

    def parse(self, response):
        """Parses the news list page."""
        # Target both hero and standard article links
        article_nodes = response.css('h3 a.d-block, h2 a.d-block, .jeg_thumb a')
        self.logger.info(f"Found {len(article_nodes)} article links on {response.url}")

        has_valid_item_in_window = False
        
        # Track seen URLs in this page to avoid processing the same hero article twice
        page_seen_urls = set()

        for link in article_nodes:
            href = link.attrib.get('href')
            if not href or href in page_seen_urls:
                continue
            url = response.urljoin(href)
            page_seen_urls.add(href)

            # Improved date extraction with fallback for hero articles
            card_root = link.xpath(
                "./ancestor::*[self::article "
                "or self::div[contains(@class,'news-card-info') or contains(@class,'news-card-style') "
                "or contains(@class,'jeg_post') or contains(@class,'post') or contains(@class,'jeg_hero')]][1]"
            )
            
            publish_time = self._parse_card_date(card_root)

            # Core logic: Should we process this article?
            is_valid = self.should_process(url, publish_time)
            
            if not is_valid:
                continue
            
            # CRITICAL: Only allow pagination if we have a CONFIRMED recent date
            # This prevents infinite pagination when dates fail to parse
            if publish_time and publish_time >= self.cutoff_date:
                has_valid_item_in_window = True
            elif publish_time is None and not self.is_already_scraped(url):
                # If date is unknown but it's a new URL, we still crawl it but don't use it to trigger next page
                pass
            
            yield scrapy.Request(
                url,
                callback=self.parse_detail,
                dont_filter=self.full_scan,
                meta={"publish_time_hint": publish_time}
            )

        # Pagination: If we found valid items or dates were unknown, try the next page
        next_page = response.css('.pagination li.next a::attr(href)').get()
        if next_page and has_valid_item_in_window:
            yield response.follow(next_page, callback=self.parse, dont_filter=True)

    def parse_detail(self, response):
        """
        Standardized detail parsing using the base class helper.
        """
        yield self.auto_parse_item(response)
