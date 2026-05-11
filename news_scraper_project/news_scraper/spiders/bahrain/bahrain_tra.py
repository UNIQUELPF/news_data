import dateparser
import scrapy
from news_scraper.spiders.smart_spider import SmartSpider

class BahrainTraSpider(SmartSpider):
    """
    Refactored Bahrain TRA (Telecommunications Regulatory Authority) Spider.
    Uses SmartSpider for high-fidelity content extraction.
    """
    name = "bahrain_tra"
    source_timezone = 'Asia/Bahrain'
    
    country_code = 'BHR'
    country = '巴林'
    organization = 'TRA Bahrain'
    
    allowed_domains = ["tra.org.bh"]
    start_urls = [
        "https://www.tra.org.bh/category/press-releases/",
    ]
    
    # Precise selector for the main content
    fallback_content_selector = "main"

    # Listing page has no dates; allow processing without dates
    strict_date_required = False

    async def start(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing, dont_filter=True)

    def parse_listing(self, response):
        # TRA uses article links like /article/some-title
        has_valid_item_in_window = False

        for href in response.css("a[href*='/article/']::attr(href)").getall():
            url = response.urljoin(href.strip())

            # SmartSpider handles the deduplication and cutoff logic
            if not self.should_process(url, None):
                continue

            has_valid_item_in_window = True
            yield scrapy.Request(url, callback=self.parse_detail, dont_filter=self.full_scan)

    def parse_detail(self, response):
        # 1. Metadata Extraction
        title = response.css(".page-title::text, main h2::text").get() \
                or response.xpath("//meta[@property='og:title']/@content").get()
        
        if title:
            title = title.strip()
            # Filter out generic category names
            if title in ["البيانات الصحفية", "Press Releases"]:
                return

        # 2. Extract publish_time from page (Arabic format: "05 يناير 2026")
        publish_time = None
        date_text = response.css(".date-time::text").get()
        if date_text:
            date_text = date_text.strip()
            parsed = dateparser.parse(date_text, languages=["ar"], settings={"TIMEZONE": "UTC"})
            if parsed:
                publish_time = parsed.replace(tzinfo=None)

        # 3. Content Extraction (Rich Content Mode)
        content_data = self.extract_content(response)
        if not content_data["content_plain"]:
            return

        # 4. Assemble V2 Item
        yield {
            "url": response.url,
            "title": title,
            "raw_html": response.text,
            "language": "ar", # Primary language is Arabic
            "section": "press_release",
            "organization": self.organization,
            "country_code": self.country_code,
            "country": self.country,
            **content_data,
            "publish_time": publish_time, # Override content_data's publish_time
        }
