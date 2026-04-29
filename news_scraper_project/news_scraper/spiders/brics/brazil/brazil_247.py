# 巴西247爬虫，使用 V2 现代化架构 (Sitemap + Smart Extraction)
import scrapy
from datetime import datetime
import pytz
from news_scraper.spiders.smart_spider import SmartSpider
from scrapy.spiders import SitemapSpider

class Brazil247Spider(SitemapSpider, SmartSpider):
    name = "brazil_247"
    country_code = 'BRA'
    country = '巴西'
    allowed_domains = ["brasil247.com"]
    target_table = "bra_247"
    
    # Using Sitemap for high-fidelity discovery
    sitemap_urls = ['https://www.brasil247.com/sitemaps/sitemap.xml']
    sitemap_rules = [
        (r'/(?!sitemaps|author|video|tv|blog|cultura|esportes)[a-z0-9-]+/.+', 'parse_detail'),
    ]

    # SmartSpider settings
    use_curl_cffi = True
    fallback_content_selector = "article.article__full"
    language = 'pt'
    source_timezone = 'America/Sao_Paulo'
    
    def __init__(self, *args, **kwargs):
        # Initialize both parents
        super(Brazil247Spider, self).__init__(*args, **kwargs)
        
    def start_requests(self):
        """Ensure sitemap requests are never filtered by Redis."""
        for url in self.sitemap_urls:
            yield scrapy.Request(url, self._parse_sitemap, dont_filter=True)
        
    def sitemap_filter(self, entries):
        """
        Ultra-Fast Pre-filtering: 
        Uses string comparison for ISO dates to avoid the massive overhead of dateparser
        when processing 100k+ sitemap entries.
        """
        # Pre-format cutoff as string for lightning-fast comparison
        cutoff_str = None
        if hasattr(self, 'cutoff_date') and self.cutoff_date:
            cutoff_str = self.cutoff_date.isoformat()

        for entry in entries:
            lastmod = entry.get('lastmod')
            if lastmod and cutoff_str:
                # ISO date strings (YYYY-MM-DD...) can be compared directly
                if lastmod < cutoff_str:
                    continue
            yield entry

    def parse_detail(self, response):
        """
        Parses the article detail page using standardized SmartSpider extraction.
        """
        # 1. Surgical extraction using Master Wrapper
        item = self.auto_parse_item(
            response, 
            publish_time_xpath="//time[contains(@class, 'article__time')]/@dateTime | //time[contains(@class, 'article__time')]/@datetime | //time[contains(@class, 'article__time')]/text()"
        )
        
        if not item:
            return

        # 2. Manual Image Recovery & Prioritization (for og:image)
        # ContentEngine sometimes picks up ads/logos (e.g. Dinheiro 3D).
        # We must ensure the og:image is ALWAYS the primary (first) image.
        featured_image = response.xpath("//meta[@property='og:image']/@content").get()
        if featured_image:
            current_images = item.get('images') or []
            if featured_image not in current_images:
                item['images'] = [featured_image] + current_images
            elif current_images[0] != featured_image:
                # Move it to the front
                current_images.remove(featured_image)
                item['images'] = [featured_image] + current_images

        # 3. Metadata refinement
        item['country'] = self.country
        item['country_code'] = self.country_code
        item['author'] = item.get('author') or "Brasil 247"
        
        # 3. Incremental check (Sliding Window)
        # For SitemapSpider, we check inside parse_detail
        if not self.should_process(response.url, item.get('publish_time')):
            self.logger.info(f"Skipping old article: {response.url}")
            return

        yield item
