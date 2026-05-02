import scrapy
import re
from datetime import datetime
from news_scraper.spiders.smart_spider import SmartSpider

class IndonesiaKompasMoneySpider(SmartSpider):
    name = "indonesia_kompas_money"
    country_code = 'IDN'
    country = '印度尼西亚'
    language = 'id'
    allowed_domains = ["indeks.kompas.com", "money.kompas.com", "kompas.com"]
    target_table = "idn_kompas_money"
    
    source_timezone = 'Asia/Jakarta'
    use_curl_cffi = True
    
    fallback_content_selector = ".read__content"

    custom_settings = {
        "DOWNLOAD_DELAY": 1.0,
        "CONCURRENT_REQUESTS": 2,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        # 1. Main index
        yield scrapy.Request(
            url="https://indeks.kompas.com/?site=money&page=1",
            callback=self.parse_list,
            meta={'current_page': 1},
            dont_filter=True
        )
        
        # 2. Modern Sitemap Discovery
        sitemap_urls = [
            "https://money.kompas.com/sitemap-archive-money.xml",
            "https://money.kompas.com/sitemap-news-money.xml",
        ]
        for url in sitemap_urls:
            yield scrapy.Request(url, callback=self.parse_sitemap)

    def parse_list(self, response):
        current_page = response.meta.get('current_page', 1)
        # Extract links from the index
        links = response.css('a.article-link::attr(href)').getall()
        
        new_links_found = 0
        valid_article_links = []

        for link in set(links):
            if '/read/' in link:
                full_url = response.urljoin(link)
                publish_time_hint = self._extract_date_from_url(full_url)
                
                if publish_time_hint:
                    if publish_time_hint.date() < self.cutoff_date.date():
                        self.logger.info(f"STOPPING: Article date {publish_time_hint.date()} is older than cutoff {self.cutoff_date.date()}. URL: {full_url}")
                        continue

                if self.should_process(full_url, publish_time_hint):
                    valid_article_links.append((full_url, publish_time_hint))

        for full_url, time_hint in valid_article_links:
            new_links_found += 1
            yield scrapy.Request(
                full_url, 
                callback=self.parse_detail,
                meta={'publish_time_hint': time_hint}
            )
        
        # Pagination
        all_dates_on_page = []
        for link in set(links):
             if '/read/' in link:
                 dt = self._extract_date_from_url(link)
                 if dt: all_dates_on_page.append(dt)

        should_continue = False
        if all_dates_on_page:
            oldest_date = min(all_dates_on_page).date()
            should_continue = (oldest_date >= self.cutoff_date.date())
            self.logger.info(f"PAGE {current_page}: {len(links)} links, oldest={oldest_date}, continue={should_continue}")

        if should_continue:
            next_page = current_page + 1
            next_url = f"https://indeks.kompas.com/?site=money&page={next_page}"
            yield scrapy.Request(
                url=next_url,
                callback=self.parse_list,
                meta={'current_page': next_page},
                dont_filter=True
            )

    def parse_sitemap(self, response):
        import re
        links = re.findall(r'<loc>(?:<!\[CDATA\[)?(https?://[^\]<> ]+)(?:\]\]>)?</loc>', response.text)
        
        for link in links:
            if "money.kompas.com/read/" in link:
                publish_time_hint = self._extract_date_from_url(link)
                if publish_time_hint and publish_time_hint.date() < self.cutoff_date.date():
                    continue
                
                if self.should_process(link, publish_time_hint):
                    yield scrapy.Request(link, callback=self.parse_detail)

    def parse_detail(self, response):
        # V2 automatic extraction
        item = self.auto_parse_item(
            response,
            title_xpath="//h1[contains(@class, 'read__title')]/text()",
            publish_time_xpath="//meta[@name='content_PublishedDate']/@content | //div[contains(@class, 'read__time')]/text()"
        )

        item['author'] = response.css("div.credit-title-name::text").get() or "Kompas.com"
        item['section'] = "Money"
        
        # Prioritize og:image for cover compatibility
        og_image = response.xpath("//meta[@property='og:image']/@content").get()
        if og_image:
            item.setdefault('images', []).insert(0, response.urljoin(og_image))

        # Date filter
        if item.get('publish_time'):
            if item['publish_time'].date() < self.cutoff_date.date():
                return

        yield item

    def _extract_date_from_url(self, url):
        """Helper to extract date from Kompas.com URL structure: /read/YYYY/MM/DD/
        Returns a naive datetime. No timezone conversion - URL dates are calendar dates."""
        match = re.search(r"/read/(\d{4})/(\d{2})/(\d{2})/", url)
        if match:
            year, month, day = map(int, match.groups())
            try:
                return datetime(year, month, day)
            except Exception:
                pass
        return None
