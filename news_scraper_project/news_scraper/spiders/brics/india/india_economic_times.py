import scrapy
import re
from datetime import datetime
from news_scraper.spiders.smart_spider import SmartSpider

class IndiaEconomicTimesSpider(SmartSpider):
    name = "india_economic_times"
    country_code = 'IND'
    country = '印度'
    language = 'en'
    allowed_domains = ["economictimes.indiatimes.com"]
    target_table = "ind_economic_times"
    
    source_timezone = 'Asia/Kolkata'
    use_curl_cffi = True
    
    fallback_content_selector = ".artText, .article_content, .Normal, .artText-fixed"

    # Section configurations: (section_name, msid)
    # Using the lazyload interface for more efficient crawling
    SECTIONS = [
        ("india", "81582957"),
        ("agriculture", "1202099874"),
        ("finance", "1286551815"),
        ("policy", "1106944246"),
        ("foreign-trade", "1200949414"),
    ]

    custom_settings = {
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "AUTOTHROTTLE_ENABLED": True,
    }

    def start_requests(self):
        for section_name, msid in self.SECTIONS:
            # Lazyload URL format: lazyloadlistnew.cms?msid={msid}&curpg={page}&img=1
            list_url = f"https://economictimes.indiatimes.com/lazyloadlistnew.cms?msid={msid}&curpg=1&img=1"
            yield scrapy.Request(
                list_url,
                callback=self.parse_list,
                dont_filter=True,
                meta={
                    'section_hint': section_name,
                    'msid': msid,
                    'page': 1
                }
            )

    def parse_list(self, response):
        section = response.meta['section_hint']
        msid = response.meta['msid']
        page = response.meta['page']

        articles = response.css('div.eachStory')
        if not articles:
            self.logger.info(f"[{section}] No articles found on page {page}, stopping.")
            return

        has_valid_item_in_window = False
        for article in articles:
            link = article.css('a::attr(href)').get()
            if not link:
                continue
            url = response.urljoin(link)

            # Date format in lazyload: "Apr 29, 2026, 04:07 PM IST"
            date_el = article.css('time.date-format::attr(data-time)').get()
            publish_time = None
            if date_el:
                try:
                    publish_time = self.parse_to_utc(datetime.strptime(date_el.strip(), "%b %d, %Y, %I:%M %p IST"))
                except Exception as e:
                    self.logger.debug(f"Date parsing failed for {date_el}: {e}")

            if self.should_process(url, publish_time):
                has_valid_item_in_window = True
                yield scrapy.Request(
                    url,
                    callback=self.parse_detail,
                    meta={'section_hint': section, 'publish_time_hint': publish_time}
                )

        # Pagination logic
        if has_valid_item_in_window:
            next_page = page + 1
            if next_page <= 50: # Practical limit for lazyload pagination
                next_url = f"https://economictimes.indiatimes.com/lazyloadlistnew.cms?msid={msid}&curpg={next_page}&img=1"
                yield scrapy.Request(
                    next_url,
                    callback=self.parse_list,
                    meta={
                        'section_hint': section,
                        'msid': msid,
                        'page': next_page
                    }
                )

    def parse_detail(self, response):
        """Parses the detail page of an article."""
        item = self.auto_parse_item(
            response,
            title_xpath="//h1/text() | //h1[contains(@class, 'artTitle')]/text()",
            publish_time_xpath="//time[contains(@class, 'jsdtTime')]/text() | //time[@class='date-format']/@data-time"
        )

        # Priority og:image
        og_image = response.xpath("//meta[@property='og:image']/@content").get()
        if og_image:
            if not item.get('images'):
                item['images'] = []
            if og_image not in item['images']:
                item['images'].insert(0, og_image)

        # Final publish_time cleaning (sometimes it has prefixes)
        if isinstance(item.get('publish_time'), str):
            try:
                clean_time = re.sub(r'^(Last Updated:|Updated:|Published:)', '', item['publish_time']).strip()
                parsed = datetime.strptime(clean_time, "%b %d, %Y, %I:%M:%S %p IST")
                item['publish_time'] = self.parse_to_utc(parsed)
            except:
                pass

        # Stop if older than cutoff
        if not self.full_scan and item['publish_time'] and item['publish_time'] < self.cutoff_date:
            return

        item['author'] = response.css('.artByline a::text, .publish_by::text').get() or "Economic Times Staff"
        item['country_code'] = self.country_code
        item['country'] = self.country
        
        yield item
