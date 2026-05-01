import scrapy
import re
from datetime import datetime
from bs4 import BeautifulSoup
from news_scraper.spiders.smart_spider import SmartSpider

class EgyptMubasherSpider(SmartSpider):
    name = 'egypt_mubasher'
    country_code = 'EGY'
    country = '埃及'
    allowed_domains = ['english.mubasher.info']
    target_table = 'egy_mubasher'

    # SmartSpider Settings
    use_curl_cffi = True
    language = 'en'
    source_timezone = 'Africa/Cairo'
    fallback_content_selector = ".article-body, .md-news-details__content, article, .the-news"

    def start_requests(self):
        url = "https://english.mubasher.info/news/sa/now/latest"
        yield scrapy.Request(url, callback=self.parse_list, dont_filter=True, meta={'page': 1})

    def parse_list(self, response):
        raw_html = response.text
        # Use selector for more precise extraction of pairs (url + date)
        cards = response.css('.mi-article-media-block__content')
        
        if not cards:
            self.logger.warning(f"No cards found via CSS on {response.url}. Stopping to avoid undated crawl.")
            return

        self.logger.info(f"Found {len(cards)} articles on {response.url}")
        has_valid_item_in_window = False
        
        for card in cards:
            link = card.css('.mi-article-media-block__title::attr(href)').get()
            if not link:
                continue
                
            url = response.urljoin(link)
            date_text = card.css('.mi-article-media-block__date::text').get()
            
            publish_time = None
            if date_text:
                import dateparser
                # Mubasher format usually like "28 April 04:56 PM"
                publish_time = dateparser.parse(date_text, settings={'TIMEZONE': 'UTC', 'RETURN_AS_TIMEZONE_AWARE': False})
            
            publish_time_utc = self.parse_to_utc(publish_time) if publish_time else None

            if self.should_process(url, publish_time_utc):
                has_valid_item_in_window = True
                meta_dict = {'publish_time_hint': publish_time_utc}
                if getattr(self, 'playwright', False):
                    meta_dict['playwright'] = True
                yield scrapy.Request(url, callback=self.parse_detail, meta=meta_dict)

        if has_valid_item_in_window:
            page = response.meta.get('page', 1)
            num_pages_match = re.search(r'window\.midata\.numPages\s*=\s*(\d+)', raw_html)
            max_pages = int(num_pages_match.group(1)) if num_pages_match else 100

            if page < max_pages:
                next_page = page + 1
                next_url = f"https://english.mubasher.info/news/sa/now/latest//{next_page}"
                yield scrapy.Request(next_url, callback=self.parse_list, dont_filter=True, meta={'page': next_page})

    def parse_detail(self, response):
        raw_html = response.text
        match = re.search(r"window\.article\s*=\s*(\{[\s\S]*?\})\s*;", raw_html)

        title = None
        publish_time_extracted = None
        content = None

        if match:
            raw_js = match.group(1)
            
            title_match = re.search(r"'title'\s*:\s*'((?:[^'\\]|\\.)*)'", raw_js)
            if not title_match:
                title_match = re.search(r'"title"\s*:\s*"((?:[^"\\]|\\.)*)"', raw_js)
            if title_match:
                title = title_match.group(1).replace("\\'", "'").replace('\\"', '"')

            date_match = re.search(r"'publishedAt'\s*:\s*'([^']+)'", raw_js)
            if not date_match:
                date_match = re.search(r'"publishedAt"\s*:\s*"([^"]+)"', raw_js)
            if date_match:
                date_str = date_match.group(1)
                try:
                    publish_time_extracted = datetime.fromisoformat(date_str.replace('Z', '+00:00')).replace(tzinfo=None)
                except Exception:
                    pass

            body_match = re.search(r"'body'\s*:\s*'((?:[^'\\]|\\.)*)'", raw_js)
            if not body_match:
                body_match = re.search(r'"body"\s*:\s*"((?:[^"\\]|\\.)*)"', raw_js)
            if body_match:
                body_html = body_match.group(1).replace("\\'", "'").replace('\\"', '"').replace('\\/', '/')
                body_soup = BeautifulSoup(body_html, 'html.parser')
                content = body_soup.get_text(separator='\n\n', strip=True)

        item = self.auto_parse_item(
            response,
            title_xpath=None,
            publish_time_xpath=None
        )
        if not item:
            return

        if title:
            item['title'] = title
            
        if publish_time_extracted:
            item['publish_time'] = self.parse_to_utc(publish_time_extracted)
            
        if content:
            item['content'] = content

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

        item['author'] = item.get('author') or "Mubasher"

        yield item
