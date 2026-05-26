# 巴西247爬虫，使用 V2 现代化架构 (Sitemap + Smart Extraction)
import scrapy
import re
from scrapy.spiders import SitemapSpider
from scrapy.utils.sitemap import Sitemap
from news_scraper.spiders.smart_spider import SmartSpider


class Brazil247Spider(SitemapSpider, SmartSpider):
    name = "brazil_247"
    country_code = "BRA"
    country = "巴西"
    language = "pt"
    source_timezone = "America/Sao_Paulo"
    allowed_domains = ["brasil247.com"]
    dateparser_settings = {"DATE_ORDER": "DMY"}

    use_curl_cffi = True
    fallback_content_selector = "article.article__full"

    sitemap_urls = ["https://www.brasil247.com/sitemaps/sitemap.xml"]
    sitemap_rules = [
        (r"/(?!sitemaps|author|video|tv|blog|cultura|esportes)[a-z0-9-]+/.+", "parse_detail"),
    ]

    def __init__(self, *args, **kwargs):
        super(Brazil247Spider, self).__init__(*args, **kwargs)

    async def start(self):
        for url in self.sitemap_urls:
            yield scrapy.Request(url, self._parse_sitemap, dont_filter=True)

    def _parse_sitemap(self, response):
        if response.url.endswith("/sitemap.xml"):
            body = self._get_sitemap_body(response)
            if not body:
                self.logger.warning(f"Ignoring invalid sitemap index: {response.url}")
                return
            
            s = Sitemap(body)
            if s.type == "sitemapindex":
                urls = [entry['loc'] for entry in s if 'loc' in entry]
                
                # Sort sitemaps so sitemap-today.xml is first, then sitemap-57.xml.gz, sitemap-56.xml.gz, ..., sitemap-0.xml.gz
                def get_sitemap_num(url):
                    if 'today' in url:
                        return 999999
                    match = re.search(r'sitemap-(\d+)', url)
                    return int(match.group(1)) if match else -1
                
                sorted_urls = sorted(urls, key=get_sitemap_num, reverse=True)
                
                if sorted_urls:
                    first_url = sorted_urls[0]
                    self.logger.info(f"Sitemap index parsed. Starting sequential crawl with: {first_url}")
                    yield scrapy.Request(
                        first_url, 
                        callback=self.parse_sitemap_sequential, 
                        priority=100,
                        meta={'remaining_sitemaps': sorted_urls[1:]}
                    )
            return

        # Fallback to standard _parse_sitemap if not the main index
        for req in super()._parse_sitemap(response):
            yield req

    def parse_sitemap_sequential(self, response):
        body = self._get_sitemap_body(response)
        if not body:
            self.logger.warning(f"Ignoring invalid sitemap: {response.url}")
            return

        s = Sitemap(body)
        
        has_new_articles = False
        cutoff_str = self.cutoff_date.isoformat() if getattr(self, "cutoff_date", None) else None
        
        valid_entries = []
        for entry in s:
            loc = entry.get("loc")
            if not loc:
                continue
            lastmod = entry.get("lastmod")
            
            # Filter by date
            if lastmod and cutoff_str and lastmod < cutoff_str:
                continue
            
            valid_entries.append(entry)
            has_new_articles = True

        self.logger.info(f"Parsed sitemap {response.url}: found {len(valid_entries)}/{len(list(Sitemap(body)))} valid entries (cutoff: {cutoff_str})")

        # Yield requests for details
        for entry in valid_entries:
            loc = entry['loc']
            for r, c in self._cbs:
                if r.search(loc):
                    yield scrapy.Request(
                        loc, 
                        callback=c,
                        meta={
                            "playwright": True
                        },
                        dont_filter=self.full_scan
                    )
                    break

        # Chain to next sitemap if we found new articles in the current one and have remaining sitemaps
        remaining = response.meta.get('remaining_sitemaps', [])
        if has_new_articles and remaining:
            next_url = remaining[0]
            self.logger.info(f"Sitemap {response.url} has new/valid articles. Continuing crawl with next sitemap: {next_url}")
            yield scrapy.Request(
                next_url,
                callback=self.parse_sitemap_sequential,
                priority=100,
                meta={'remaining_sitemaps': remaining[1:]}
            )
        else:
            self.logger.info(f"Stopping sitemap crawl at {response.url}. has_new_articles={has_new_articles}, remaining={len(remaining)}")

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
