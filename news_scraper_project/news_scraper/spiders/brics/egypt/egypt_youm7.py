import scrapy
import dateparser
from news_scraper.spiders.smart_spider import SmartSpider

class EgyptYoum7Spider(SmartSpider):
    name = 'egypt_youm7'
    country_code = 'EGY'
    country = '埃及'
    allowed_domains = ['youm7.com']
    target_table = 'egy_youm7'

    # SmartSpider Settings
    use_curl_cffi = True
    language = 'ar'
    source_timezone = 'Africa/Cairo'
    fallback_content_selector = "#articleBody, .articleCont, .article-content"

    def start_requests(self):
        url = "https://www.youm7.com/Section/%D8%A7%D9%82%D8%AA%D8%B5%D8%A7%D8%AF-%D9%88%D8%A8%D9%88%D8%B1%D8%B5%D8%A9/297/1"
        yield scrapy.Request(url, callback=self.parse_list, dont_filter=True, meta={'page': 1})

    def parse_list(self, response):
        articles = response.css('.bigOneSec, .secArticle, div[class*=col-xs-12] .secArticle')
        if not articles:
            articles = response.css('.secArticle')
        
        if not articles:
            self.logger.info("No articles found on page. Stopping.")
            return

        has_valid_item_in_window = False
        
        for article in articles:
            a_elem = article.css('a')
            if not a_elem:
                continue
                
            a_elem = a_elem[0]
            link = a_elem.attrib.get('href') or a_elem.css('::attr(href)').get()
            if not link:
                continue
                
            url = response.urljoin(link)
            
            # The date is hidden in data-id: "4/29/2026 6:00:00 AM"
            raw_date = article.attrib.get('data-id')
            if not raw_date:
                raw_date = article.css('.newsDate2::text, .strDate::text, .articleDate::text, .time::text').get()
                
            if not raw_date:
                self.logger.warning(f"Missing date in listing for {url}")
                continue
                
            # Use Auto-detect date parsing. (DO NOT pass languages=['ar'] if we have English format)
            parsed_date = dateparser.parse(raw_date.strip())
            if not parsed_date:
                self.logger.error(f"STRICT STOP: Could not parse date {raw_date}. Breaking to avoid backfill.")
                break
                
            publish_time = self.parse_to_utc(parsed_date)

            if self.should_process(url, publish_time):
                has_valid_item_in_window = True
                meta_dict = {'publish_time_hint': publish_time}
                if getattr(self, 'playwright', False):
                    meta_dict['playwright'] = True
                yield scrapy.Request(url, callback=self.parse_detail, meta=meta_dict)

        if has_valid_item_in_window:
            page = response.meta.get('page', 1) + 1
            if page < 300: # Safety cap
                next_url = f"https://www.youm7.com/Section/%D8%A7%D9%82%D8%AA%D8%B5%D8%A7%D8%AF-%D9%88%D8%A8%D9%88%D8%B1%D8%B5%D8%A9/297/{page}"
                yield scrapy.Request(next_url, callback=self.parse_list, dont_filter=True, meta={'page': page})

    def parse_detail(self, response):
        item = self.auto_parse_item(
            response,
            publish_time_xpath="//meta[@property='article:published_time']/@content"
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
                
        # youm7 author usually in .writeName or something, auto_parse_item might miss
        author = response.css('span.writeName::text, .writeName *::text').get()
        if author:
            item['author'] = author.strip()
        else:
            item['author'] = item.get('author') or "youm7"

        yield item
