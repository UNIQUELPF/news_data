# 阿联酋fxnewstoday爬虫，负责抓取对应站点、机构或栏目内容。

import scrapy
from news_scraper.spiders.smart_spider import SmartSpider
from datetime import datetime
import re

class UaeFxNewsTodaySpider(SmartSpider):
    name = "uae_fxnewstoday"

    country_code = 'ARE'
    country = '阿联酋'
    language = 'ar'
    source_timezone = 'Asia/Dubai' # UAE Time
    use_curl_cffi = True
    
    # Selective selectors for FX News Today
    fallback_content_selector = ".desc-text, .article-content, .content-article"
    
    allowed_domains = ["fxnewstoday.ae"]

    custom_settings = {
        'DOWNLOAD_DELAY': 1.0,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 4,
        'RANDOMIZE_DOWNLOAD_DELAY': True,
        'DOWNLOADER_MIDDLEWARES': {
            'news_scraper.middlewares.CurlCffiMiddleware': 500,
        }
    }

    def start_requests(self):
        url = "https://www.fxnewstoday.ae/latest-news"
        yield scrapy.Request(url, callback=self.parse_list, meta={'page': 1})

    def parse_list(self, response):
        # Use CSS for article discovery
        articles = response.css('div.mb-2, div.card, article, div.news-item')
        if not articles:
            # Fallback for direct link search if structure is complex
            articles = response.xpath("//a[contains(@href, '-') and re:test(@href, '-\\d{5,8}$')]/parent::*")

        has_valid_item_in_window = False
        
        for article in articles:
            # Look for link
            link_node = article.css('a[href*="-"]::attr(href)').get()
            if not link_node:
                continue
                
            url = response.urljoin(link_node)
            
            # Date extraction from list page text
            text = article.get()
            date_str = self._extract_date_from_text(text)
            
            publish_time = self.parse_date(date_str)
            
            if not self.should_process(url, publish_time):
                continue
                
            has_valid_item_in_window = True
            
            yield scrapy.Request(
                url,
                callback=self.parse_detail,
                meta={'publish_time': publish_time}
            )

        # Pagination logic using "Load More" cursor if available
        if has_valid_item_in_window:
            load_more = response.css('#LoadMoreBtn::attr(data-cursor)').get()
            if load_more:
                next_url = response.urljoin(load_more)
                yield scrapy.Request(next_url, callback=self.parse_list)

    def parse_detail(self, response):
        # Automated extraction using SmartSpider V2
        item = self.auto_parse_item(
            response,
            title_xpath="//h1//text()",
            publish_time_xpath="//time/@datetime"
        )
        
        # Override metadata if list page had better info
        if response.meta.get('publish_time') and not item.get('publish_time'):
            item['publish_time'] = response.meta['publish_time']
            
        # Ensure image is captured for financial news
        if not item.get('images'):
            og_image = response.xpath("//meta[@property='og:image']/@content").get()
            if og_image:
                item['images'] = [response.urljoin(og_image)]
        
        # Force language and country
        item['language'] = self.language
        item['country'] = self.country
        item['section'] = 'Latest News'
        
        yield item

    def _extract_date_from_text(self, text):
        if not text:
            return None
        # Match YYYY-MM-DD HH:MM or YYYY-MM-DD
        match = re.search(r'\d{4}-\d{2}-\d{2}(\s+\d{2}:\d{2})?', text)
        return match.group(0) if match else None
