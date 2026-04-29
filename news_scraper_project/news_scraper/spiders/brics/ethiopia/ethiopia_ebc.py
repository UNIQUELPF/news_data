import scrapy
import re
from datetime import datetime
from news_scraper.spiders.smart_spider import SmartSpider

class EthiopiaEBCSpider(SmartSpider):
    name = "ethiopia_ebc"
    country_code = 'ETH'
    country = '埃塞俄比亚'
    allowed_domains = ["ebc.et"]
    target_table = "ethi_ebc"
    
    language = 'am' # Amharic
    source_timezone = 'Africa/Cairo' # Ethiopia is UTC+3
    fallback_content_selector = ".post-content, .article-content, .description, #main-content"

    custom_settings = {
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "AUTOTHROTTLE_ENABLED": True,
    }

    def start_requests(self):
        # CatId=3 is usually News
        url = "https://www.ebc.et/Home/CategorialNews?CatId=3"
        yield scrapy.Request(url, callback=self.parse_list, dont_filter=True, meta={'page': 1})

    def _extract_date(self, text):
        if not text:
            return None
            
        # Amharic month mapping (Ethiopian Calendar)
        # 1: መስከረም, 2: ጥቅምት, 3: ኅዳር, 4: ታኅሣሥ, 5: ጥር, 6: የካቲት, 7: መጋቢት, 8: ሚያዝያ, 9: ግንቦት, 10: ሰኔ, 11: ሐምሌ, 12: ነሐሴ
        amharic_months = {
            'መስከረም': 9, 'ጥቅምት': 10, 'ኅዳር': 11, 'ታኅሣሥ': 12, 'ጥር': 1, 'የካቲት': 2, 'መጋቢት': 3, 'ሚያዝያ': 4, 'ግንቦት': 5, 'ሰኔ': 6, 'ሐምሌ': 7, 'ነሐሴ': 8
        }
        
        # Strategy 1: Check for Amharic months and Ethiopian year
        for am_month, m_num in amharic_months.items():
            if am_month in text:
                year_match = re.search(r'(20\d{2})', text)
                day_match = re.search(r'\b(\d{1,2})\b', text)
                if year_match and day_match:
                    try:
                        eyear = int(year_match.group(1))
                        eday = int(day_match.group(1))
                        # Ethiopian to Gregorian approximation: Add 8 years and 4 months
                        # This is accurate enough for ordering and Panic Break
                        return datetime(eyear + 8, m_num, eday)
                    except:
                        pass

        # Strategy 2: Look for image path date pattern /2026/4/29/
        # LIMIT this to specific strings, not the whole body text
        img_match = re.search(r'/(\d{4})/(\d{1,2})/(\d{1,2})/', text)
        if img_match:
            try:
                return datetime(int(img_match.group(1)), int(img_match.group(2)), int(img_match.group(3)))
            except:
                pass

        # Strategy 3: Match standard English format (fallback)
        match = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2}, 20\d\d', text)
        if match:
            import dateparser
            return dateparser.parse(match.group(), settings={'TIMEZONE': 'UTC'})
        return None

    def parse_list(self, response):
        posts = response.css('article.post')
        if not posts:
            self.logger.warning(f"No news posts found on {response.url}")
            return

        seen_urls = response.meta.get('seen_urls', set())
        new_urls_on_this_page = 0
        has_valid_item_in_window = False
        
        for post in posts:
            link_el = post.css('a[href*="NewsDetails?NewsId="]')
            if not link_el:
                continue
                
            href = link_el.attrib.get('href')
            url = response.urljoin(href)
            
            if url not in seen_urls:
                new_urls_on_this_page += 1
                seen_urls.add(url)
            
            # Extract date from image src WITHIN this post card
            img_src = post.css('img::attr(src)').get() or ""
            # Also check text just in case
            date_text = "".join(post.xpath('.//text()').getall())
            
            publish_time = self._extract_date(img_src) or self._extract_date(date_text)
            publish_time_utc = self.parse_to_utc(publish_time) if publish_time else None

            if self.should_process(url, publish_time_utc):
                has_valid_item_in_window = True
                meta_dict = {'publish_time_hint': publish_time_utc}
                yield scrapy.Request(url, callback=self.parse_detail, meta=meta_dict)

        if has_valid_item_in_window and new_urls_on_this_page > 0:
            page = response.meta.get('page', 1)
            if page < 100: # Safety limit
                next_page = page + 1
                next_url = f"https://www.ebc.et/Home/CategorialNews?CatId=3&page={next_page}"
                yield scrapy.Request(
                    next_url, 
                    callback=self.parse_list, 
                    meta={'page': next_page, 'seen_urls': seen_urls}
                )
        else:
            if new_urls_on_this_page == 0:
                self.logger.info(f"Duplicate page detected at page {response.meta.get('page', 1)}. Stopping pagination.")
            else:
                self.logger.info(f"No more valid items in window. Stopping pagination.")

    def parse_detail(self, response):
        item = self.auto_parse_item(
            response,
            title_xpath="//meta[@property='og:title']/@content",
        )
        
        # Ensure the main image is captured
        og_image = response.xpath("//meta[@property='og:image']/@content").get()
        if og_image:
            if not item.get('images'):
                item['images'] = []
            if og_image not in item['images']:
                item['images'].insert(0, og_image)
        
        # Secondary date check on detail page if list missed it
        if not item['publish_time']:
            # ONLY check the featured image and main content for date, 
            # to avoid picking up dates from sidebars
            og_image = response.xpath("//meta[@property='og:image']/@content").get()
            featured_img = response.css('.featured-image img::attr(src), .post-content img::attr(src)').get()
            all_text = "".join(response.xpath("//body//text()").getall()[:2000])
            
            # Priority: Featured Image URL > Content Text
            item['publish_time'] = self.parse_to_utc(
                self._extract_date(og_image) or 
                self._extract_date(featured_img) or 
                self._extract_date(all_text)
            )

        # Determine language based on content (Amharic vs English)
        text_for_lang = (item.get('title') or '') + (item.get('content_plain') or '')
        if re.search(r"[\u1200-\u137F]", text_for_lang):
            item['language'] = 'am'
        else:
            item['language'] = 'en'

        # Stop processing if older than cutoff (unless full_scan)
        if not self.full_scan and item['publish_time'] and item['publish_time'] < self.cutoff_date:
            return

        item['author'] = response.css('.author::text, .writer::text').get() or "EBC"
        item['country_code'] = self.country_code
        item['country'] = self.country
        yield item
