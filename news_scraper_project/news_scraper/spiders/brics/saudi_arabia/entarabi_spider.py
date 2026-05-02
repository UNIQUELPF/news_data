import html
import json
from datetime import datetime
import scrapy
from news_scraper.spiders.smart_spider import SmartSpider

class EntarabiSpider(SmartSpider):
    """
    Spider for Entarabi.com (Saudi Arabia).
    Uses the WordPress REST API for robust pagination and data extraction.
    """
    name = "saudi_entarabi"
    country_code = 'SAU'
    country = '沙特阿拉伯'
    language = 'ar'
    
    # Standard settings for high performance
    custom_settings = {
        "DOWNLOAD_DELAY": 0.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 5,
        "RANDOMIZE_DOWNLOAD_DELAY": True,
    }

    def start_requests(self):
        url = "https://entarabi.com/wp-json/wp/v2/posts?page=1&per_page=100&_embed=1"
        yield scrapy.Request(
            url=url,
            callback=self.parse_api,
            meta={'page': 1},
            dont_filter=True
        )

    def parse_api(self, response):
        if response.status == 400:
            self.logger.info("Reached the end of pagination.")
            return

        try:
            data = json.loads(response.text)
        except json.JSONDecodeError:
            self.logger.error("Failed to parse JSON response.")
            return

        if not isinstance(data, list) or not data:
            return

        self.logger.info(f"Page {response.meta['page']} loaded {len(data)} items.")
        
        has_valid_item_in_window = False
        for item in data:
            url = item.get("link")
            
            # Publish time extraction from API
            date_str = item.get("date")  # Format: "2026-03-23T23:59:51"
            publish_time = None
            if date_str:
                try:
                    publish_time = datetime.fromisoformat(date_str)
                    publish_time = self.parse_to_utc(publish_time)
                except ValueError:
                    pass

            if not self.should_process(url, publish_time):
                if publish_time and publish_time < self.cutoff_date:
                    self.logger.info(f"Hit date boundary at {publish_time}. Stopping pagination.")
                    has_valid_item_in_window = False
                    break
                continue
            
            has_valid_item_in_window = True

            # Extract category from _embedded
            section = "عام"
            embedded = item.get("_embedded", {})
            terms = embedded.get("wp:term", [])
            for term_group in terms:
                for term in term_group:
                    if term.get("taxonomy") == "category":
                        section = html.unescape(term.get("name", "عام"))
                        break
                if section != "عام":
                    break

            # Extract author
            author = "فريق إنت عربي"
            authors = embedded.get("author", [])
            if authors and len(authors) > 0:
                author_name = authors[0].get("name")
                if author_name:
                    author = html.unescape(author_name)

            # Title
            title_html = item.get("title", {}).get("rendered", "")
            title = html.unescape(title_html).strip() if title_html else "No Title"

            # Extract Featured Image from _embedded
            images = []
            featured_media = embedded.get("wp:featuredmedia", [])
            if featured_media and isinstance(featured_media, list) and len(featured_media) > 0:
                featured_image_url = featured_media[0].get("source_url")
                if featured_image_url:
                    images.append({"url": featured_image_url, "alt": title})

            # Content Extraction via ContentEngine
            content_html = item.get("content", {}).get("rendered", "")
            content_data = self.extract_content_from_html(content_html, url)
            
            # Merge images from content_data
            if content_data.get("images"):
                for img in content_data["images"]:
                    img_url = img.get("url") if isinstance(img, dict) else img
                    if img_url and img_url not in images:
                        images.append(img_url)

            # Ensure all images are strings
            images = [img.get("url") if isinstance(img, dict) else img for img in images]

            yield {
                "url": url,
                "title": title,
                "publish_time": publish_time,
                "author": author,
                "language": self.language,
                "section": section,
                "country_code": self.country_code,
                "country": self.country,
                **content_data,
                "images": images
            }

        # Pagination
        if has_valid_item_in_window:
            next_page = response.meta['page'] + 1
            next_url = f"https://entarabi.com/wp-json/wp/v2/posts?page={next_page}&per_page=100&_embed=1"
            yield scrapy.Request(
                url=next_url,
                callback=self.parse_api,
                meta={'page': next_page},
                dont_filter=True
            )

    def extract_content_from_html(self, content_html, url):
        """Helper to use ContentEngine on raw HTML string."""
        from pipeline.content_engine import ContentEngine
        return ContentEngine.process(
            raw_html=f"<html><body>{content_html}</body></html>",
            base_url=url
        )
