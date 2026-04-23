import json
import scrapy
import dateparser
from bs4 import BeautifulSoup
from news_scraper.spiders.smart_spider import SmartSpider

class BahrainCbbSpider(SmartSpider):
    """
    Lean & Modernized Bahrain CBB Spider.
    Supports automated paging and relies on SmartSpider for core logic.
    """
    name = "bahrain_cbb"
    source_timezone = 'Asia/Bahrain'
    
    country_code = 'BHR'
    country = '巴林'
    
    allowed_domains = ["cbb.gov.bh"]
    ajax_url = "https://www.cbb.gov.bh/wp-admin/admin-ajax.php"
    
    custom_settings = {
        "CONCURRENT_REQUESTS": 1,  # Single thread to avoid triggering WAF
        "DOWNLOAD_DELAY": 3,       # 3 seconds between requests
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 2,
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 60000,
    }
    
    # CSS selector for the main content area (used for fidelity-mode extraction)
    fallback_content_selector = ".single-media-item-content, main"

    feeds = [
        {"mf-types[]": "press_release", "section": "press_release"},
        {"mf-categories[]": "treasury-bills", "section": "government_securities"},
    ]

    def start_requests(self):
        for feed in self.feeds:
            yield self._build_ajax_request(feed, page=1)

    def _build_ajax_request(self, feed, page):
        formdata = {
            "action": "get_media_posts",
            "mf-page": str(page),
            "mf-display": "list",
        }
        formdata.update(feed)
        return scrapy.FormRequest(
            self.ajax_url,
            formdata=formdata,
            callback=self.parse_listing,
            dont_filter=True,  # Allow listing pages to refresh
            meta={
                "feed": feed,
                "page": page,
                "feed_section": feed["section"]
            },
        )

    def parse_listing(self, response):
        try:
            payload = json.loads(response.text)
            html = payload.get("html", "")
            if not html:
                return
        except Exception as e:
            self.logger.error(f"Invalid AJAX response: {e}")
            return

        soup = BeautifulSoup(html, "html.parser")
        items = soup.select(".cbb-media-list-item")
        
        has_valid_item_in_window = False
        
        for item in items:
            link_node = item.select_one(".media-item-title a")
            if not link_node: continue
            
            url = response.urljoin(link_node.get("href"))
            
            # Pre-parse date for early stopping
            date_node = item.select_one(".media-item-title-top")
            date_text = " ".join(date_node.stripped_strings) if date_node else ""
            dt_local = dateparser.parse(date_text, languages=["en"])
            publish_time = self.parse_to_utc(dt_local)

            # Check if we should crawl this URL
            if not self.should_process(url, publish_time):
                continue
            
            has_valid_item_in_window = True
            
            yield scrapy.Request(
                url,
                callback=self.parse_detail,
                dont_filter=self.full_scan,
                meta={
                    "publish_time_hint": publish_time,
                    "section_hint": response.meta["feed_section"],
                    "playwright": True,
                    "playwright_context_kwargs": {
                        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                    },
                    "playwright_page_goto_kwargs": {
                        "wait_until": "networkidle",
                    },
                },
                headers={
                    "Referer": "https://www.cbb.gov.bh/media-center/",
                }
            )

        # Automated Paging: If we found valid items on this page, try the next one
        if has_valid_item_in_window:
            next_page = response.meta["page"] + 1
            # Safety limit is now handled by should_process and earliest_date, 
            # but we keep a loose upper bound of 500 pages to prevent infinite loops.
            if next_page <= 500:
                yield self._build_ajax_request(response.meta["feed"], next_page)

    def parse_detail(self, response):
        """
        Simplified detail parsing. Standard metadata and content are handled 
        automatically by the base class.
        """
        yield self.auto_parse_item(response)
