import scrapy
import dateparser
import re
from news_scraper.spiders.smart_spider import SmartSpider

class AlbaniaFinanceSpider(SmartSpider):
    """
    Modernized Ministry of Finance Albania Spider.
    """
    name = 'albania_finance'
    source_timezone = 'Europe/Tirane'
    
    country_code = 'ALB'
    country = '阿尔巴尼亚'
    
    allowed_domains = ['financa.gov.al']
    custom_settings = {
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 1,
    }

    use_curl_cffi = True

    async def start(self):
        for url in ['https://financa.gov.al/newsrooms/lajme/']:
            yield scrapy.Request(url, callback=self.parse, dont_filter=True)
    
    fallback_content_selector = "article, .entry-content, .post-content"

    def parse(self, response):
        """Parses the news list page."""
        # Force use of Selector to ensure fresh parsing
        from scrapy import Selector
        sel = Selector(text=response.text)
        
        # Use XPath for maximum robustness
        articles = sel.xpath("//article | //*[contains(@class, 'news-item')]")
        self.logger.info(f"Found {len(articles)} potential items via XPath on {response.url}")

        has_valid_item_in_window = False
        for article in articles:
            # Try multiple XPath variants for title and date
            title_node = article.xpath(".//a[contains(@class, 'news-item__title')] | .//h2/a")
            date_node = article.xpath(".//time[contains(@class, 'posted-on')] | .//*[contains(@class, 'news-item__date')]")
            
            if title_node and date_node:
                url = response.urljoin(title_node.xpath("./@href").get())
                # Extract all text and join to handle line breaks
                date_str = " ".join(date_node.xpath('.//text()').getall()).strip()
                
                # Clean prefix "POSTUAR MË:" and bullet points
                date_str = re.sub(r'[•·\s]*POSTUAR MË:\s*', '', date_str, flags=re.IGNORECASE)
                date_str = re.sub(r'\s+', ' ', date_str).strip()
                
                # Use dateparser to handle Albanian months
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

        if has_valid_item_in_window:
            next_page = sel.xpath("//a[contains(@class, 'next') and contains(@class, 'page-numbers')]/@href | //a[contains(@class, 'nextpostslink')]/@href").get()
            if next_page:
                yield response.follow(next_page, callback=self.parse, dont_filter=True)

    def parse_detail(self, response):
        """Standardized detail parsing."""
        yield self.auto_parse_item(response)

