import scrapy
from datetime import datetime
import re
from news_scraper.spiders.smart_spider import SmartSpider


class PlaceraSESpider(SmartSpider):
    """
    瑞典 Placera.se 新闻爬虫
    策略：通过 sitemap.xml 获取文章 URL 列表，再逐个抓详情页
    """
    name = "se_placera"
    source_timezone = 'Europe/Stockholm'

    country_code = 'SWE'
    country = '瑞典'
    language = 'sv'
    strict_date_required = True

    allowed_domains = ['placera.se']
    use_curl_cffi = True

    fallback_content_selector = "article"

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.0,
        'CONCURRENT_REQUESTS': 8,
    }

    async def start(self):
        """Initial request: fetch sitemap index."""
        yield scrapy.Request(
            'https://www.placera.se/sitemap.xml',
            callback=self.parse_sitemap_index,
            dont_filter=True,
        )

    def parse_sitemap_index(self, response):
        """Parse sitemap index, find 2026 monthly sitemaps."""
        sel = scrapy.Selector(response, type='xml')
        sel.remove_namespaces()
        urls = sel.css('loc::text').getall()

        for url in urls:
            if '2026-' in url:
                self.logger.info(f"Found 2026 sitemap: {url}")
                yield scrapy.Request(
                    url,
                    callback=self.parse_monthly_sitemap,
                )

    def parse_monthly_sitemap(self, response):
        """Parse monthly sitemap, extract article URLs with date filtering."""
        sel = scrapy.Selector(response, type='xml')
        sel.remove_namespaces()
        url_nodes = sel.css('url')

        self.logger.info(f"Monthly sitemap: {len(url_nodes)} URLs found")

        has_valid_item_in_window = False

        for node in url_nodes:
            loc = node.css('loc::text').get()
            if not loc or '/nyheter/' not in loc:
                continue

            # Extract date: try sitemap lastmod first, then URL pattern
            publish_time = None
            lastmod = node.css('lastmod::text').get()
            if lastmod:
                try:
                    dt_obj = datetime.fromisoformat(lastmod.replace('Z', '+00:00'))
                    publish_time = self.parse_to_utc(dt_obj)
                except (ValueError, TypeError):
                    pass

            if not publish_time:
                date_match = re.search(r'(\d{4}-\d{2}-\d{2})', loc)
                if date_match:
                    try:
                        dt_obj = datetime.strptime(date_match.group(1), '%Y-%m-%d')
                        publish_time = self.parse_to_utc(dt_obj)
                    except ValueError:
                        pass

            if not self.should_process(loc, publish_time):
                continue

            has_valid_item_in_window = True
            yield scrapy.Request(
                loc,
                callback=self.parse_detail,
                meta={"publish_time_hint": publish_time},
            )

    def parse_detail(self, response):
        """Parse article detail page using standardized extraction."""
        item = self.auto_parse_item(response)

        # Clean title: remove " | Placera.se" suffix
        if item.get('title'):
            item['title'] = re.sub(r'\s*\|\s*Placera\.se$', '', item['title']).strip()

        # Content length check: skip very short pages
        content = item.get('content_plain', '') or ''
        if len(content.strip()) < 50:
            self.logger.debug(f"Skipping (short content): {response.url}")
            return

        item['author'] = 'Placera'
        item['section'] = 'Nyheter'

        yield item
