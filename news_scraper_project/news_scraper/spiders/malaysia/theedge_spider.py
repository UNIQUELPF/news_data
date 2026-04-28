import json
from datetime import datetime

import scrapy
from news_scraper.spiders.smart_spider import SmartSpider
from bs4 import BeautifulSoup
from news_scraper.items import NewsItem


class TheEdgeSpider(SmartSpider):
    name = "malaysia_theedge"

    country_code = "MYS"

    country = "马来西亚"
    language = "en"
    source_timezone = "Asia/Kuala_Lumpur"
    start_date = "2026-01-01"
    allowed_domains = ["theedgemalaysia.com"]
    
    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 0.5,
    }

    # Categories to scrape. For now just 'economy' as requested.
    CATEGORIES = [
        {'id': 'economy', 'name': 'Economy'}
    ]




    def iter_start_requests(self):
        for cat in self.CATEGORIES:
            # Offset starts at 0
            url = f"https://theedgemalaysia.com/api/loadMoreCategories?offset=0&categories={cat['id']}"
            yield scrapy.Request(url, callback=self.parse_list, meta={'cat': cat, 'offset': 0})

    def start_requests(self):
        yield from self.iter_start_requests()

    async def start(self):
        for request in self.iter_start_requests():
            yield request

    def parse_list(self, response):
        cat = response.meta['cat']
        offset = response.meta['offset']
        
        try:
            data = json.loads(response.text)
            items = data.get('results', [])
        except Exception as e:
            self.logger.error(f"Failed to parse JSON from {response.url}: {e}")
            return
            
        if not items:
            self.logger.info(f"No items found for offset {offset} in category {cat['name']}")
            return
            
        self.logger.info(f"Offset {offset} for {cat['name']}: found {len(items)} items")
            
        oldest_on_page = None
        
        for item in items:
            title = item.get('title')
            nid = item.get('nid')
            # Permalinks look like "/node/797240"
            permalink = item.get('permalink')
            if not permalink and nid:
                permalink = f"/node/{nid}"
            
            if not permalink:
                continue
                
            url = f"https://theedgemalaysia.com{permalink}"
            
            # Timestamp is in milliseconds
            created_ms = item.get('created')
            if not created_ms:
                continue
            
            # Some entries might have it in seconds or ms. 1774365617000 is ms.
            if created_ms > 10**11: # If it's 13 digits, it's ms
                dt = datetime.fromtimestamp(created_ms / 1000)
            else:
                dt = datetime.fromtimestamp(created_ms)
                
            if oldest_on_page is None or dt < oldest_on_page:
                oldest_on_page = dt
                
            if dt >= self.cutoff_date:
                yield scrapy.Request(
                    url, 
                    callback=self.parse_article,
                    meta={
                        'title': title,
                        'publish_time': dt,
                        'section': cat['name']
                    }
                )
                
        # Pagination
        if oldest_on_page and oldest_on_page >= self.cutoff_date:
            next_offset = offset + 10 # Default limit appears to be 10
            next_url = f"https://theedgemalaysia.com/api/loadMoreCategories?offset={next_offset}&categories={cat['id']}"
            yield scrapy.Request(next_url, callback=self.parse_list, meta={'cat': cat, 'offset': next_offset})
        else:
            self.logger.info(f"Reached cutoff or end of content for {cat['name']} at offset {offset}")

    def parse_article(self, response):
        title = response.meta['title']
        publish_time = response.meta['publish_time']
        section = response.meta['section']
        
        # We try to extract from __NEXT_DATA__ first for robustness, then fallback to selectors
        try:
            start_marker = '<script id="__NEXT_DATA__" type="application/json">'
            if start_marker in response.text:
                start_index = response.text.find(start_marker) + len(start_marker)
                end_index = response.text.find('</script>', start_index)
                json_text = response.text[start_index:end_index]
                data = json.loads(json_text)
                node_data = data['props']['pageProps']['data']
                
                # Update title and pub_time if available in JSON for better accuracy
                if node_data.get('title'):
                    title = node_data.get('title')
                
                # Content is in node_data['content'] as an HTML string
                content_html = node_data.get('content', '')
                if not content_html: # Fallback to node_data['body'] just in case
                    content_html = node_data.get('body', '')
                    
                soup = BeautifulSoup(content_html, 'html.parser')
                content_text = soup.get_text("\n\n").strip()
                
                author = node_data.get('author', '')
            else:
                # Fallback to selectors if __NEXT_DATA__ is missing
                content_text = "\n\n".join(response.css('.newsTextDataWrapInner p ::text').getall())
                author = response.css('.news-detail_authorName__8i7pP ::text').get() or ""
        except Exception as e:
            self.logger.error(f"Failed to extract article via JSON for {response.url}: {e}")
            # Minimum fallback
            content_text = "\n\n".join(response.css('.newsTextDataWrapInner p ::text').getall())
            author = ""

        if not content_text:
            self.logger.warning(f"No content extracted for {response.url}")
            # Final fallback to standard content selector text
            content_text = response.css('.newsTextDataWrapInner ::text').getall()
            content_text = "\n".join([t.strip() for t in content_text if t.strip()])

        item = NewsItem()
        item['title'] = title
        item['url'] = response.url
        item['publish_time'] = publish_time.strftime("%Y-%m-%d %H:%M:%S")
        item['author'] = author.strip() if author else ""
        item['content'] = content_text
        item['section'] = section
        item['language'] = "en"
        
        yield item
