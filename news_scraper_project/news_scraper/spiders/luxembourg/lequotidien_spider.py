import logging

import dateparser
import scrapy
from bs4 import BeautifulSoup
from news_scraper.spiders.smart_spider import SmartSpider

logger = logging.getLogger(__name__)


class LeQuotidienSpider(SmartSpider):
    """
    V2: Scrapes the Le Quotidien (lequotidien.lu) news site.
    Uses standard WP-like server-side rendering pagination.
    """
    name = "luxembourg_lequotidien"
    source_timezone = 'Europe/Luxembourg'

    country_code = 'LUX'
    country = '卢森堡'
    language = 'fr'

    allowed_domains = ["lequotidien.lu"]

    custom_settings = {
        'DOWNLOAD_DELAY': 0.5,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 8,
    }

    fallback_content_selector = 'article.post-listing, div#main-content'

    start_categories = [
        'a-la-une', 'luxembourg', 'politique-societe', 'economie',
        'monde', 'grande-region', 'police-justice', 'sport-national',
        'culture', 'lifestyle'
    ]

    async def start(self):
        """Initial requests entry point."""
        for cat in self.start_categories:
            url = f"https://lequotidien.lu/{cat}/page/1/"
            yield scrapy.Request(
                url=url,
                callback=self.parse,
                cb_kwargs={"cat": cat, "page": 1},
                dont_filter=True
            )

    def parse(self, response, cat, page):
        """Parse listing page: extract article blocks with date/title and yield detail requests."""
        soup = BeautifulSoup(response.text, "html.parser")

        main_container = soup.select_one('#main-content') or soup.select_one('main') or soup.find(id='content') or soup
        articles = main_container.find_all('article')

        if not articles:
            logger.info(f"No articles found on {cat} page {page}. Stopping.")
            return

        has_valid_item_in_window = False

        for p in articles:
            a_tag = p.find('a')
            if not a_tag or not a_tag.get('href'):
                continue

            href = a_tag.get('href')
            detail_url = href if href.startswith('http') else f"https://lequotidien.lu{href}"

            # Extract date
            date_el = p.select_one('.tie-date') or p.select_one('time') or p.select_one('.date')
            date_text = date_el.text.strip() if date_el else ""

            # Extract title
            title_el = p.find(['h2', 'h3'])
            title = title_el.text.strip() if title_el else ""

            if not date_text or not title:
                continue

            # Parse date (European DMY) and convert to UTC
            publish_time = None
            try:
                dt_obj = dateparser.parse(date_text, settings={'DATE_ORDER': 'DMY'})
                if dt_obj:
                    publish_time = self.parse_to_utc(dt_obj)
            except Exception:
                continue

            if not publish_time:
                continue

            # V2 deduplication and incremental check
            if not self.should_process(detail_url, publish_time):
                continue

            has_valid_item_in_window = True

            yield scrapy.Request(
                url=detail_url,
                callback=self.parse_detail,
                meta={
                    "publish_time_hint": publish_time,
                    "title_hint": title,
                    "section_hint": cat
                },
                dont_filter=self.full_scan
            )

        # Pagination: continue while items are within the date window
        if has_valid_item_in_window:
            next_page = page + 1
            next_url = f"https://lequotidien.lu/{cat}/page/{next_page}/"
            yield scrapy.Request(
                url=next_url,
                callback=self.parse,
                cb_kwargs={"cat": cat, "page": next_page},
                dont_filter=True
            )
        else:
            logger.info(f"Reached cutoff for {cat} at page {page}. Stopping.")

    def parse_detail(self, response):
        """Parse article detail page using standardized SmartSpider extraction."""
        item = self.auto_parse_item(response)

        # Override with listing-page hints (more reliable than detail page extraction)
        title_hint = response.meta.get("title_hint")
        publish_time_hint = response.meta.get("publish_time_hint")

        if title_hint:
            item['title'] = title_hint
        if publish_time_hint:
            item['publish_time'] = publish_time_hint

        # Extract author from detail page
        author = "Le Quotidien"
        soup = BeautifulSoup(response.text, "html.parser")
        author_el = soup.select_one('.author-name') or soup.select_one('.post-meta-author')
        if author_el:
            author = author_el.get_text(separator=" ", strip=True)

        item['author'] = author
        item['language'] = 'fr'

        yield item
