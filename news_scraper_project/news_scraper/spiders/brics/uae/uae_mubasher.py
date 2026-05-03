# 阿联酋mubasher爬虫，负责抓取对应站点、机构或栏目内容。

import scrapy
from news_scraper.spiders.smart_spider import SmartSpider
from datetime import datetime

class UaeMubasherSpider(SmartSpider):
    name = "uae_mubasher"

    country_code = 'ARE'
    country = '阿联酋'
    language = 'ar'
    source_timezone = 'Asia/Dubai'
    use_curl_cffi = True
    
    fallback_content_selector = ".article__content-text, .mi-article__body"
    
    allowed_domains = ["mubasher.info"]

    custom_settings = {
        'DOWNLOAD_DELAY': 1.0,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 2,
        'RANDOMIZE_DOWNLOAD_DELAY': True,
        'DOWNLOADER_MIDDLEWARES': {
            'news_scraper.middlewares.CurlCffiMiddleware': 500,
        }
    }

    def start_requests(self):
        url = "https://www.mubasher.info/news/sa/now/latest"
        yield scrapy.Request(url, callback=self.parse_list, meta={'page': 1})

    def parse_list(self, response):
        # The main card container that includes both the metadata and the visible date
        articles = response.css('.mi-article-media-block')
        if not articles:
            return

        has_valid_item_in_window = False
        
        for article in articles:
            # Title and URL are often in the <a> tag within the block
            title_tag = article.css('.mi-article-media-block__title')
            url_path = title_tag.attrib.get('href')
            if not url_path:
                # Fallback to the data attribute if title_tag is missing
                url_path = article.css('div[data-url]::attr(data-url)').get()
            
            if not url_path:
                continue
                
            url = response.urljoin(url_path)
            title = title_tag.css('::text').get() or article.css('div[data-title]::attr(data-title)').get()
            if title:
                title = title.strip()
            
            # Extract date from the list page
            date_str = article.css('.mi-article-media-block__date::text').get()
            publish_time = self.parse_date(date_str)
            
            if not self.should_process(url, publish_time):
                continue
                
            self.logger.info(f"Processing: {title} ({date_str})")
            has_valid_item_in_window = True
            
            yield scrapy.Request(
                url,
                callback=self.parse_detail,
                meta={'title': title, 'publish_time_hint': publish_time}
            )

        # Pagination using the robust has_valid_item_in_window logic
        if has_valid_item_in_window:
            current_page = response.meta.get('page', 1)
            next_page = current_page + 1
            next_url = f"https://www.mubasher.info/news/sa/now/latest//{next_page}"
            yield scrapy.Request(next_url, callback=self.parse_list, meta={'page': next_page})

    def parse_detail(self, response):
        item = self.auto_parse_item(
            response,
            title_xpath="//h1//text()",
            publish_time_xpath="//time/@datetime"
        )
        
        # Check window
        if not self.should_process(response.url, item.get('publish_time')):
            return
            
        item['author'] = "Mubasher"
        item['section'] = "Latest"
        
        yield item
