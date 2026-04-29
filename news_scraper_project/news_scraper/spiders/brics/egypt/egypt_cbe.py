import scrapy
import re
from datetime import datetime
from w3lib.html import remove_tags
from news_scraper.spiders.smart_spider import SmartSpider

class EgyptCbeSpider(SmartSpider):
    name = "egypt_cbe"
    country_code = 'EGY'
    country = '埃及'
    allowed_domains = ["cbe.org.eg"]
    target_table = "egy_cbe"

    # SmartSpider Settings
    use_curl_cffi = True
    language = 'en' # dynamic per article
    source_timezone = 'Africa/Cairo'
    fallback_content_selector = ".cbe-rich-text, .content, .details, article, .news-details, #main-content"

    def start_requests(self):
        url = "https://www.cbe.org.eg/sitemap.xml"
        yield scrapy.Request(url, callback=self.parse_list, dont_filter=True)

    def parse_list(self, response):
        xml = response.text
        urls = re.findall(r'<loc>(.*?)</loc>', xml)
        
        news_urls = [u for u in urls if '/news-publications/news/' in u]
        self.logger.info(f"Filtered down to {len(news_urls)} news URLs")
        
        has_valid_item = False
        
        for url in news_urls:
            # We enforce scraping both /en/ and /ar/ articles
            # The date is embedded in the URL: /news-publications/news/2026/04/28/15/30/...
            pub_time = None
            match = re.search(r'/(\d{4})/(\d{2})/(\d{2})/(\d{2})/(\d{2})/', url)
            if match:
                dt_str = f"{match.group(1)}-{match.group(2)}-{match.group(3)} {match.group(4)}:{match.group(5)}:00"
                pub_time = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
            else:
                match2 = re.search(r'/(\d{4})/(\d{2})/(\d{2})/', url)
                if match2:
                    pub_time = datetime(int(match2.group(1)), int(match2.group(2)), int(match2.group(3)))
                else:
                    continue
                    
            publish_time_utc = self.parse_to_utc(pub_time)

            if self.should_process(url, publish_time_utc):
                has_valid_item = True
                meta_dict = {'publish_time_hint': publish_time_utc}
                if getattr(self, 'playwright', False):
                    meta_dict['playwright'] = True
                yield scrapy.Request(url, callback=self.parse_detail, meta=meta_dict)

    def parse_detail(self, response):
        # Override language dynamically
        self.language = 'ar' if '/ar/' in response.url else 'en'
        
        item = self.auto_parse_item(
            response,
            title_xpath="//h1/text() | //*[contains(@class, 'article-title')]/text() | //*[contains(@class, 'cbe-title')]/text() | //h2/text()",
            publish_time_xpath=None # Handled by hint
        )
        if not item:
            return

        featured_image = response.xpath("//meta[@property='og:image']/@content").get()
        if featured_image:
            current_images = item.get('images') or []
            if featured_image not in current_images:
                item['images'] = [featured_image] + current_images
            elif current_images[0] != featured_image:
                current_images.remove(featured_image)
                item['images'] = [featured_image] + current_images

        item['author'] = item.get('author') or "Central Bank of Egypt"

        yield item
