# 巴西247爬虫，使用 V2 现代化架构 (Sitemap + Smart Extraction)
import scrapy
from scrapy.spiders import SitemapSpider

from news_scraper.spiders.smart_spider import SmartSpider


class Brazil247Spider(SitemapSpider, SmartSpider):
    name = "brazil_247"
    country_code = "BRA"
    country = "巴西"
    language = "pt"
    source_timezone = "America/Sao_Paulo"
    start_date = "2026-01-01"
    allowed_domains = ["brasil247.com"]

    use_curl_cffi = True
    fallback_content_selector = "article.article__full"

    sitemap_urls = ["https://www.brasil247.com/sitemaps/sitemap.xml"]
    sitemap_rules = [
        (r"/(?!sitemaps|author|video|tv|blog|cultura|esportes)[a-z0-9-]+/.+", "parse_detail"),
    ]

    def __init__(self, *args, **kwargs):
        super(Brazil247Spider, self).__init__(*args, **kwargs)

    def start_requests(self):
        for url in self.sitemap_urls:
            yield scrapy.Request(url, self._parse_sitemap, dont_filter=True)

    def sitemap_filter(self, entries):
        cutoff_str = self.cutoff_date.isoformat() if getattr(self, "cutoff_date", None) else None
        for entry in entries:
            lastmod = entry.get("lastmod")
            if lastmod and cutoff_str and lastmod < cutoff_str:
                continue
            yield entry

    def parse_detail(self, response):
        item = self.auto_parse_item(
            response,
            publish_time_xpath=(
                "//time[contains(@class, 'article__time')]/@dateTime | "
                "//time[contains(@class, 'article__time')]/@datetime | "
                "//time[contains(@class, 'article__time')]/text()"
            ),
        )
        if not item:
            return

        featured_image = response.xpath("//meta[@property='og:image']/@content").get()
        if featured_image:
            current_images = item.get("images") or []
            if featured_image not in current_images:
                item["images"] = [featured_image] + current_images
            elif current_images[0] != featured_image:
                current_images.remove(featured_image)
                item["images"] = [featured_image] + current_images

        item["country"] = self.country
        item["country_code"] = self.country_code
        item["author"] = item.get("author") or "Brasil 247"

        if not self.should_process(response.url, item.get("publish_time")):
            self.logger.info(f"Skipping old article: {response.url}")
            return

        yield item
