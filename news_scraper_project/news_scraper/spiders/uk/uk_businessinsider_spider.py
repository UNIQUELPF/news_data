import scrapy
import json
import re
from datetime import datetime
from news_scraper.spiders.base_spider import BaseNewsSpider

class UkBusinessInsiderSpider(BaseNewsSpider):
    name = "uk_businessinsider"

    country_code = 'GBR'

    country = '英国'
    allowed_domains = ["businessinsider.com"]
    start_urls = ["https://www.businessinsider.com/economy"]
    
    target_table = "uk_businessinsider_news"

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "news_scraper.middlewares.CurlCffiMiddleware": 543,
            "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
        },
        "CURLL_CFFI_IMPERSONATE": "chrome120",
        "CONCURRENT_REQUESTS": 4,
        "DOWNLOAD_DELAY": 1
    }

    use_curl_cffi = True

    def parse(self, response):
        # 1. Parse initial articles on the page
        article_links = response.css('a.tout-title-link::attr(href), a.tout-image::attr(href)').getall()
        for link in list(set(article_links)):
            yield response.follow(link, self.parse_article)

        # 2. Extract the initial token for pagination
        next_url_attr = response.css('div[data-feed-id="economy"]::attr(data-next)').get()
        if next_url_attr:
            token_match = re.search(r'riverNextPageToken=([^&]+)', next_url_attr)
            if token_match:
                first_token = token_match.group(1)
                yield self.make_ajax_request(first_token)

    def make_ajax_request(self, token):
        ajax_url = f"https://www.businessinsider.com/ajax/content-api/vertical?templateId=legacy-river&capiVer=2&id=economy&riverSize=50&riverNextPageToken={token}&page[limit]=20"
        return scrapy.Request(ajax_url, callback=self.parse_ajax, meta={'token': token})

    def parse_ajax(self, response):
        try:
            data = json.loads(response.text)
            html_snippet = data.get('rendered', '')
            if html_snippet:
                sel = scrapy.Selector(text=html_snippet)
                links = sel.css('a::attr(href)').getall()
                for link in list(set(links)):
                    if '/202' in link or '/201' in link:
                        yield response.follow(link, self.parse_article)

            next_token = None
            next_link = data.get('links', {}).get('next', '')
            if next_link:
                token_match = re.search(r'riverNextPageToken=([^&]+)', next_link)
                if token_match:
                    next_token = token_match.group(1)
            
            if next_token:
                yield self.make_ajax_request(next_token)
                
        except Exception as e:
            self.logger.error(f"Failed to parse AJAX response: {e}")

    def parse_article(self, response):
        # Title with deep text extraction
        title = "".join(response.css('h1 *::text, .headline *::text').getall()).strip()
        
        # Date from ld+json
        pub_date = None
        json_ld = response.xpath('//script[@type="application/ld+json"]/text()').getall()
        for ld in json_ld:
            try:
                data = json.loads(ld)
                # handle both list and object
                if isinstance(data, list):
                    for obj in data:
                        if 'datePublished' in obj:
                            d_str = obj['datePublished'].split('.')[0].replace('Z', '')
                            pub_date = datetime.fromisoformat(d_str)
                            break
                elif 'datePublished' in data:
                    d_str = data['datePublished'].split('.')[0].replace('Z', '')
                    pub_date = datetime.fromisoformat(d_str)
            except:
                continue
            if pub_date: break
            
        if pub_date and not self.filter_date(pub_date):
            return

        # Extremely broad container scan to support articles & slideshows
        content_parts = response.css('section.post-content p *::text, section.post-body-content p *::text, article p *::text, div.content-lock-content p *::text, section.post-body p *::text, .post-body-content *::text').getall()
        cleaned_content = "\n\n".join([p.strip() for p in content_parts if len(p.strip()) > 10])

        if cleaned_content and title:
            yield {
                "url": response.url,
                "title": title,
                "content": cleaned_content,
                "publish_time": pub_date,
                "author": "Business Insider",
                "language": "en",
                "section": "Economy"
            }
