# 阿尔巴尼亚monitor爬虫，负责抓取对应站点、机构或栏目内容。

import re
from datetime import datetime, timedelta

import scrapy
from news_scraper.items import NewsItem
from news_scraper.utils import get_dynamic_cutoff

class AlbaniaMonitorSpider(scrapy.Spider):
    name = 'albania_monitor'

    country_code = 'ALB'

    country = '阿尔巴尼亚'
    allowed_domains = ['monitor.al']
    start_urls = ['https://monitor.al/ekonomi/']
    target_table = 'alb_monitor'

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super(AlbaniaMonitorSpider, cls).from_crawler(crawler, *args, **kwargs)
        dynamic_cutoff = get_dynamic_cutoff(crawler.settings, spider.target_table, spider_name=spider.name)
        spider.CUTOFF_DATE = max(dynamic_cutoff, datetime(2026, 1, 1)) if dynamic_cutoff else datetime(2026, 1, 1)
        return spider

    def parse(self, response):
        """Parses the news list page."""
        article_nodes = response.css('h3 a.d-block, h2 a.d-block')
        self.logger.info(f"Found {len(article_nodes)} article links on {response.url}")

        page_urls = set()
        recent_found = False
        unknown_date_found = False
        old_date_found = False

        for link in article_nodes:
            href = link.attrib.get('href')
            if not href:
                continue
            full_url = response.urljoin(href)
            if full_url in page_urls:
                continue
            page_urls.add(full_url)

            card_root = link.xpath("./ancestor::*[self::article or self::div[contains(@class,'jeg_post') or contains(@class,'post')]][1]")
            listing_text = " ".join(card_root.xpath(".//text()").getall()) if card_root else ""
            listing_publish_time = self._parse_listing_datetime(listing_text)

            if listing_publish_time:
                if listing_publish_time < self.CUTOFF_DATE:
                    old_date_found = True
                    continue
                recent_found = True
            else:
                unknown_date_found = True

            yield scrapy.Request(
                url=full_url,
                callback=self.parse_detail,
                meta={'listing_publish_time': listing_publish_time}
            )

        next_page = response.css('.pagination li.next a::attr(href)').get()
        if next_page and (recent_found or unknown_date_found):
            yield response.follow(next_page, callback=self.parse)
        elif old_date_found and not recent_found and not unknown_date_found:
            self.logger.info(f"All visible Monitor items are older than cutoff on {response.url}. Stopping pagination.")

    def parse_detail(self, response):
        """Parses the news detail page and checks cutoff."""
        date_str = response.css('meta[property="article:published_time"]::attr(content)').get()
        publish_time = response.meta.get('listing_publish_time')
        
        if not publish_time and date_str:
            try:
                date_str = date_str.split('+')[0]
                publish_time = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S")
            except Exception as e:
                self.logger.error(f"Failed to parse date {date_str} on {response.url}: {e}")
        
        if publish_time and publish_time < self.CUTOFF_DATE:
            self.logger.info(f"Reached cutoff date {self.CUTOFF_DATE} at {publish_time} on {response.url}")
            # Note: Because Scrapy requests are asynchronous, we can't easily break the pagination loop
            # from within the detail callback. However, CloseSpider extension handles graceful shutdown
            # based on item counts if needed, or we just filter out old items. To truly stop the spider
            # when reaching old items across multiple pages, a custom extension or state would be used.
            # For now, we drop the item.
            return

        item = NewsItem()
        item['url'] = response.url
        
        # Title
        item['title'] = response.css('h1::text').get(default='').strip()
        if not item['title']:
            # Fallback
            item['title'] = response.css('meta[property="og:title"]::attr(content)').get(default='')
            
        item['publish_time'] = publish_time
        item['language'] = 'sq'
        item['author'] = 'Revista Monitor'
        item['scrape_time'] = datetime.now()
        
        # Content
        content_parts = response.css('.standard-content p::text').getall()
        item['content'] = "\n\n".join([p.strip() for p in content_parts if len(p.strip()) > 10])
        
        if item['content'] and item['title']:
            yield item

    def _parse_listing_datetime(self, text):
        if not text:
            return None

        normalized = " ".join(text.split()).lower()
        now = datetime.now().replace(second=0, microsecond=0)
        patterns = [
            (r'(\d+)\s+minutes?\s+m[ëe]\s+par[ëe]', 'minutes'),
            (r'(\d+)\s+hours?\s+m[ëe]\s+par[ëe]', 'hours'),
            (r'(\d+)\s+days?\s+m[ëe]\s+par[ëe]', 'days'),
            (r'(\d+)\s+weeks?\s+m[ëe]\s+par[ëe]', 'weeks'),
        ]
        for pattern, unit in patterns:
            match = re.search(pattern, normalized)
            if not match:
                continue
            value = int(match.group(1))
            if unit == 'minutes':
                return now - timedelta(minutes=value)
            if unit == 'hours':
                return now - timedelta(hours=value)
            if unit == 'days':
                return now - timedelta(days=value)
            if unit == 'weeks':
                return now - timedelta(weeks=value)
        return None
