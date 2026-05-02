import scrapy
from news_scraper.spiders.smart_spider import SmartSpider

class IndonesiaInaNewsSpider(SmartSpider):
    name = "indonesia_ina_news"
    country_code = 'IDN'
    country = '印度尼西亚'
    language = 'en'
    allowed_domains = ["ina.go.id", "www.ina.go.id"]
    target_table = "idn_ina_news"
    
    source_timezone = 'Asia/Jakarta'
    use_curl_cffi = True
    
    # Root container for the article content as seen in the screenshot
    fallback_content_selector = "#block-ina-content"

    custom_settings = {
        "DOWNLOAD_DELAY": 1.0,
        "CONCURRENT_REQUESTS": 2,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(
            url="https://www.ina.go.id/ina-in-the-news/",
            callback=self.parse_list,
            dont_filter=True
        )

    def parse_list(self, response):
        # Use XPath for more robust element finding
        cards = response.xpath("//div[contains(@class, 'media-content_item')]")
        self.logger.info(f"Discovered {len(cards)} potential news cards on the page.")
        
        new_links_found = 0
        seen_urls = set()
        
        for card in cards:
            link = card.xpath(".//a[contains(@href, '/ina-in-the-news/')]/@href").get()
            if not link:
                continue
            
            full_url = response.urljoin(link)
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)

            if full_url.rstrip("/") == "https://www.ina.go.id/ina-in-the-news":
                continue

            # Extract date from list card as a reliable fallback
            list_date_str = card.xpath(".//div[contains(@class, 'media-content_post-date')]/text()").get()
            publish_time_hint = self.parse_date(list_date_str) if list_date_str else None
            
            # CRITICAL: Early stop if date is behind cutoff
            if publish_time_hint and not self.full_scan:
                if publish_time_hint.date() < self.cutoff_date.date():
                    self.logger.info(f"STOPPING: Article date {publish_time_hint.date()} is older than cutoff {self.cutoff_date.date()}. URL: {full_url}")
                    continue

            # Check if we should process
            if self.should_process(full_url, publish_time_hint):
                new_links_found += 1
                yield scrapy.Request(
                    full_url, 
                    callback=self.parse_detail,
                    meta={'list_date_str': list_date_str}
                )
        
        if new_links_found == 0 and len(cards) > 0:
            self.logger.warning("No NEW links found, but cards were present. All articles might be duplicates or filtered.")

    def parse_detail(self, response):
        list_date_str = response.meta.get('list_date_str')
        
        # V2 handles image/content extraction automatically
        item = self.auto_parse_item(
            response,
            title_xpath="//div[contains(@class, 'blogpost1_title-wrapper')]//h1/text()",
            publish_time_xpath="//div[contains(@class, 'blogpost1_title-wrapper')]//div[contains(@class, 'text-size-small')]/text()"
        )

        # Manually supplement images to ensure the cover is captured
        # Try og:image first as it's usually optimized for external embedding
        og_image = response.xpath("//meta[@property='og:image']/@content").get()
        
        cover_node = response.css(".blogpost1_image-wrapper img")
        cover_image = cover_node.css("::attr(src)").get()
        srcset = cover_node.css("::attr(srcset)").get()
        if srcset:
            cover_image = srcset.split(",")[-1].strip().split(" ")[0]
            
        final_cover = og_image or cover_image
        if final_cover:
            full_img_url = response.urljoin(final_cover)
            item.setdefault('images', [])
            if full_img_url not in item['images']:
                item['images'].insert(0, full_img_url)

        item['author'] = "Indonesia Investment Authority"
        item['section'] = "In the News"

        # Fallback to list date if detail page date extraction failed
        if not item.get('publish_time') and list_date_str:
            item['publish_time'] = self.parse_date(list_date_str)

        # Cutoff check
        if not self.full_scan and item.get('publish_time'):
            if item['publish_time'].date() < self.cutoff_date.date():
                return

        yield item
