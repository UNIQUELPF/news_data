import scrapy
from news_scraper.spiders.smart_spider import SmartSpider

class AfricaBusinessDaySpider(SmartSpider):
    """
    South Africa BusinessDay spider.
    Modernized V2: Uses Sitemaps for discovery and ContentEngine for extraction.
    """
    name = 'africa_businessday'
    country_code = 'ZAF'
    country = '南非'
    language = 'en'
    source_timezone = 'Africa/Johannesburg'
    use_curl_cffi = True
    fallback_content_selector = ".c-article-content"
    allowed_domains = ['businessday.co.za']

    custom_settings = {
        'DOWNLOAD_DELAY': 1,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 2,
        'RANDOMIZE_DOWNLOAD_DELAY': True,
        'DOWNLOADER_MIDDLEWARES': {
            'news_scraper.middlewares.CurlCffiMiddleware': 500,
        }
    }

    def start_requests(self):
        # We use sitemap index and section indices to reliably pull everything
        urls = [
            'https://www.businessday.co.za/arc/outboundfeeds/sitemap-news-index/',
            'https://www.businessday.co.za/arc/outboundfeeds/sitemap-section-index/',
            'https://www.businessday.co.za/arc/outboundfeeds/sitemap-index/'
        ]
        for url in urls:
            yield scrapy.Request(
                url,
                callback=self.parse_sitemap_index,
                headers={'User-Agent': 'Mozilla/5.0'},
                dont_filter=True
            )

    def parse_sitemap_index(self, response):
        # Use XPath with local-name() to be namespace-agnostic for XML sitemaps
        sitemap_urls = response.xpath('//*[local-name()="loc"]/text()').getall()
        for url in sitemap_urls:
            yield scrapy.Request(
                url,
                callback=self.parse_sitemap,
                headers={'User-Agent': 'Mozilla/5.0'},
                dont_filter=True
            )

    def parse_sitemap(self, response):
        nodes = response.xpath('//*[local-name()="url"]')
        for node in nodes:
            url = node.xpath('./*[local-name()="loc"]/text()').get()
            if not url:
                continue
            
            url = url.strip()
            # Simple pre-filter for articles based on URL format
            if '/search/?' in url or '/author/' in url:
                continue
            
            # Extract date from sitemap (lastmod or publication_date for news sitemaps)
            lastmod = node.xpath('./*[local-name()="lastmod"]/text()').get() or \
                      node.xpath('.//*[local-name()="publication_date"]/text()').get()
            
            publish_time = self.parse_date(lastmod) if lastmod else None

            if self.should_process(url, publish_time):
                yield scrapy.Request(
                    url, 
                    callback=self.parse_detail,
                    meta={'publish_time_hint': publish_time},
                    headers={'User-Agent': 'Mozilla/5.0'}
                )

    def parse_detail(self, response):
        # Standard metadata extraction using SmartSpider logic
        item = self.auto_parse_item(
            response,
            title_xpath="//h1//text()",
            publish_time_xpath="//meta[@property='article:published_time']/@content"
        )
        
        # Manual image extraction fallback (BusinessDay lead images are often missed by trafilatura)
        if not item.get('images'):
            # Priority: 1. Lead Image div, 2. OG Image meta
            lead_image = response.css(".b-lead-art img::attr(src)").get() or \
                         response.xpath("//meta[@property='og:image']/@content").get()
            if lead_image:
                item['images'] = [response.urljoin(lead_image)]
        
        # Additional author refinement if not caught by auto_parse
        if not item.get('author'):
            item['author'] = response.css('.c-article-byline__author::text, [rel="author"]::text').get()
        
        yield item
