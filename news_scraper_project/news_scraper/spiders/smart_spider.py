import scrapy
import logging
import pytz
import dateparser
from datetime import datetime, timedelta
from news_scraper.utils import _get_db_connection
from pipeline.content_engine import ContentEngine

logger = logging.getLogger(__name__)

class SmartSpider(scrapy.Spider):
    """
    New Generation Base Spider with built-in intelligence and incremental logic.
    
    Key features:
    1. Sliding window incremental crawling.
    2. Automatic content extraction via ContentEngine.
    3. Global Timezone handling (Source -> UTC).
    4. Command-line overrides for full scan or custom window.
    """
    # Domain configuration to be overridden by child spiders
    source_timezone = 'UTC'  
    fallback_content_selector = None  
    
    # Default start date if DB is empty
    default_start_date = None

    def __init__(self, full_scan=False, window_days=None, *args, **kwargs):
        super(SmartSpider, self).__init__(*args, **kwargs)
        # Parse command line arguments
        self.full_scan = str(full_scan).lower() in ("1", "true", "yes")
        self.cmd_window_days = window_days
        
        # Runtime state
        self.cutoff_date = None
        self.seen_urls = set()

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super().from_crawler(crawler, *args, **kwargs)
        spider._init_incremental_state(crawler.settings)
        return spider

    def _init_incremental_state(self, settings):
        """Calculate cutoff_date and load seen_urls for deduplication."""
        # 1. Determine the absolute historical floor from settings or cmd args
        default_start_str = getattr(self, 'start_date', None) or settings.get("DEFAULT_START_DATE", "2024-01-01")
        try:
            self.earliest_date = datetime.strptime(default_start_str, "%Y-%m-%d")
        except ValueError:
            self.earliest_date = datetime(2024, 1, 1)
        
        # 2. Handle Force Full Scan
        if self.full_scan:
            self.cutoff_date = self.earliest_date
            logger.info(f"[{self.name}] FULL SCAN triggered. Starting from {self.cutoff_date}")
        else:
            # 3. Normal Incremental Calculation
            latest_time = self._fetch_latest_publish_time(settings)
            
            if not latest_time:
                self.cutoff_date = self.earliest_date
                logger.info(f"[{self.name}] NO HISTORY. Initializing from {self.cutoff_date}")
            else:
                # Calculate window (Command line arg > Settings > Default 7)
                window = int(self.cmd_window_days or settings.get("INCREMENTAL_WINDOW_DAYS", 7))
                # Ensure latest_time is naive for comparison
                if latest_time.tzinfo:
                    latest_time = latest_time.replace(tzinfo=None)
                self.cutoff_date = latest_time - timedelta(days=window)
                logger.info(f"[{self.name}] INCREMENTAL MODE. Latest DB record: {latest_time}, Window: {window}d, Cutoff: {self.cutoff_date}")

        # 4. Load recent URLs for deduplication
        # Note: In a larger setup, this should be replaced by Redis Bloom Filter
        self.seen_urls = self._fetch_recent_urls(settings)
        logger.info(f"[{self.name}] Loaded {len(self.seen_urls)} recent URLs for deduplication.")

    def _fetch_latest_publish_time(self, settings):
        """Query the unified articles table for the latest publish_time of this spider."""
        try:
            conn = _get_db_connection(settings)
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT MAX(a.publish_time) 
                    FROM articles a
                    JOIN sources s ON s.id = a.source_id
                    WHERE s.spider_name = %s
                """, (self.name,))
                res = cur.fetchone()
                conn.close()
                return res[0] if res and res[0] else None
        except Exception as e:
            logger.error(f"[{self.name}] Error fetching latest publish time: {e}")
            return None

    def _fetch_recent_urls(self, settings, limit=5000):
        """Load recent URLs from the database to prevent duplicate requests."""
        try:
            conn = _get_db_connection(settings)
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT a.source_url 
                    FROM articles a
                    JOIN sources s ON s.id = a.source_id
                    WHERE s.spider_name = %s
                    ORDER BY a.publish_time DESC NULLS LAST, a.id DESC
                    LIMIT %s
                """, (self.name, limit))
                rows = cur.fetchall()
                conn.close()
                return {row[0] for row in rows if row[0]}
        except Exception as e:
            logger.error(f"[{self.name}] Error fetching recent URLs: {e}")
            return set()

    def parse_to_utc(self, dt_obj):
        """
        Convert a datetime object (naive or aware) to a naive UTC datetime.
        Uses self.source_timezone if the object is naive.
        """
        if not dt_obj:
            return None
        
        try:
            # 1. Localize if naive
            if dt_obj.tzinfo is None:
                local_tz = pytz.timezone(self.source_timezone)
                dt_obj = local_tz.localize(dt_obj)
                
            # 2. Convert to UTC
            dt_utc = dt_obj.astimezone(pytz.UTC)
            
            # 3. Return as naive UTC for DB storage (standard convention)
            return dt_utc.replace(tzinfo=None)
        except Exception as e:
            logger.warning(f"[{self.name}] Timezone conversion failed for {dt_obj}: {e}")
            return dt_obj.replace(tzinfo=None) if dt_obj.tzinfo else dt_obj

    def should_process(self, url: str, publish_time: datetime = None) -> bool:
        """
        Determines if a URL should be processed.
        - Full Scan: Processes everything down to the earliest_date floor.
        - Incremental: Processes new URLs within the sliding window (cutoff_date).
        """
        # 1. Absolute floor: Never process anything older than our project start date
        if publish_time and publish_time < self.earliest_date:
            return False

        # 2. If full scan, we ignore deduplication and sliding window
        if self.full_scan:
            return True
        
        # 3. Incremental: Deduplication check
        if self.is_already_scraped(url):
            return False
            
        # 4. Incremental: Sliding window check (e.g. 7 days back from last record)
        if publish_time and publish_time < self.cutoff_date:
            return False
            
        return True

    def auto_parse_item(self, response, title_xpath=None, publish_time_xpath=None):
        """
        High-level helper to automate the extraction of a V2 article item.
        Handles metadata (title, time) with fallbacks and calls the content engine.
        """
        # 1. Title Extraction
        title = None
        if title_xpath:
            title = response.xpath(title_xpath).get()
        
        if not title:
            # Standard meta tags are usually the most reliable
            title = response.xpath("//meta[@property='og:title']/@content").get() \
                    or response.css("title::text").get()
        
        if title:
            title = title.strip()

        # 2. Publish Time Extraction
        publish_time = None
        if publish_time_xpath:
            raw_time = response.xpath(publish_time_xpath).get()
            if raw_time:
                parser_settings = getattr(self, 'dateparser_settings', None)
                publish_time = self.parse_to_utc(dateparser.parse(raw_time, settings=parser_settings))
        
        if not publish_time:
            # Try standard article meta
            raw_time = response.xpath("//meta[@property='article:published_time']/@content").get() or \
                       response.xpath("//meta[@name='publishdate']/@content").get()
            if raw_time:
                # Use class-level dateparser_settings if provided
                parser_settings = getattr(self, 'dateparser_settings', None)
                publish_time = self.parse_to_utc(dateparser.parse(raw_time, settings=parser_settings))
        
        if not publish_time:
            # Fallback to the hint from the listing page
            publish_time = response.meta.get("publish_time_hint")

        # 3. Content Extraction
        content_data = self.extract_content(response)
        
        # Use content engine's found time as last resort if we still have none
        if not publish_time and content_data.get("publish_time"):
            publish_time = content_data["publish_time"]

        # 4. Assemble standard V2 dictionary
        item = {
            "url": response.url,
            "title": title or content_data.get("title"),
            "raw_html": response.text,
            "publish_time": publish_time,
            "language": getattr(self, 'language', 'en'),
            "section": response.meta.get("section_hint", "news"),
            "country_code": getattr(self, 'country_code', None),
            "country": getattr(self, 'country', None),
            **content_data
        }
        return item

    def extract_content(self, response):
        """
        Invoke the Intelligence ContentEngine to extract cleaned HTML and Markdown.
        Can be called within the spider's parse method.
        """
        return ContentEngine.process(
            raw_html=response.text,
            base_url=response.url,
            fallback_selector=self.fallback_content_selector
        )

    def is_already_scraped(self, url: str) -> bool:
        """
        Checks if the URL has already been scraped by looking at the DB-based seen_urls.
        If full_scan is enabled, we ignore this check to allow updates.
        """
        if self.full_scan:
            return False
        return url in self.seen_urls

    def make_requests_from_url(self, url):
        """
        Override for scrapy-redis if needed.
        """
        return scrapy.Request(url, dont_filter=self.full_scan)
