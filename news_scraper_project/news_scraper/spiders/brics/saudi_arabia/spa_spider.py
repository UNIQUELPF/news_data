import json
from datetime import datetime, timezone
import scrapy
from news_scraper.spiders.smart_spider import SmartSpider

class SaudiPressAgencySpider(SmartSpider):
    """
    Saudi Press Agency (SPA) spider using Native JSON API for pagination.
    """
    name = "saudi_spa"
    country_code = 'SAU'
    country = '沙特阿拉伯'
    language = 'ar'
    
    custom_settings = {
        "DOWNLOAD_DELAY": 1,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "RANDOMIZE_DOWNLOAD_DELAY": True,
    }

    def start_requests(self):
        params_ar = "by_latest=1&per_page=50&w_content=1&w_tag=1&page=1&l=ar"
        url = f"https://portalapi.spa.gov.sa/api/v1/news?{params_ar}"
        yield scrapy.Request(
            url=url,
            callback=self.parse_api,
            meta={'page': 1, 'lang': 'ar', 'failed_count': 0},
            dont_filter=True
        )

    def parse_api(self, response):
        try:
            data = json.loads(response.text)
        except Exception as e:
            self.logger.error(f"Failed to parse API JSON on {response.url}: {e}")
            failed_count = response.meta.get('failed_count', 0) + 1
            if failed_count < 3:
                yield response.request.replace(meta={'page': response.meta['page'], 'lang': response.meta['lang'], 'failed_count': failed_count}, dont_filter=True)
            return

        items = data.get('data', [])
        self.logger.info(f"Fetched page {response.meta['page']} - items count: {len(items)}")

        if not items:
            return

        has_valid_item_in_window = False
        for item in items:
            news_id = item.get('uuid')
            title = item.get('title', '').strip()
            if not news_id:
                continue

            url = f"https://www.spa.gov.sa/N{news_id.replace('N','')}"

            # Parse publish time
            publish_time = None
            published_at = item.get('published_at')
            if published_at:
                try:
                    # API returns timestamp
                    publish_time = datetime.fromtimestamp(published_at, tz=timezone.utc)
                    publish_time = self.parse_to_utc(publish_time)
                except Exception:
                    pass

            if not self.should_process(url, publish_time):
                if publish_time and publish_time < self.cutoff_date:
                    self.logger.info(f"Hit date boundary at {publish_time}. Stopping pagination.")
                    has_valid_item_in_window = False
                    break
                continue

            has_valid_item_in_window = True

            # Extract Content via ContentEngine
            content_html = item.get('content', '')
            content_data = self.extract_content_from_html(content_html, url)

            # Section & Language
            category = item.get('category', {})
            section = category.get('name', 'عام') if isinstance(category, dict) else 'عام'
            lang = item.get('locale', response.meta['lang'])

            # Normalize images: Extract from API 'image' field and 'content'
            images = []
            main_image = item.get('image', {})
            if isinstance(main_image, dict):
                main_image_url = main_image.get('path')
                if main_image_url:
                    images.append(main_image_url)

            # Extract images from content_data
            raw_content_images = content_data.get("images", [])
            for img in raw_content_images:
                img_url = img.get("url") if isinstance(img, dict) else img
                if img_url and img_url not in images:
                    images.append(img_url)

            yield {
                "url": url,
                "title": title,
                "publish_time": publish_time,
                "author": "وكالة الأنباء السعودية",
                "language": lang,
                "section": section,
                "country_code": self.country_code,
                "country": self.country,
                **content_data,
                "images": images
            }

        # Pagination
        if has_valid_item_in_window:
            current_page = response.meta['page']
            meta_pagination = data.get('meta', {})
            last_page = meta_pagination.get('last_page', 999999)
            
            if current_page < last_page:
                next_page = current_page + 1
                params = f"by_latest=1&per_page=50&w_content=1&w_tag=1&page={next_page}&l={response.meta['lang']}"
                next_url = f"https://portalapi.spa.gov.sa/api/v1/news?{params}"
                
                yield scrapy.Request(
                    url=next_url,
                    callback=self.parse_api,
                    meta={'page': next_page, 'lang': response.meta['lang'], 'failed_count': 0},
                    dont_filter=True
                )

    def extract_content_from_html(self, content_html, url):
        """Helper to use ContentEngine on raw HTML string."""
        from pipeline.content_engine import ContentEngine
        return ContentEngine.process(
            raw_html=f"<html><body>{content_html}</body></html>",
            base_url=url
        )
