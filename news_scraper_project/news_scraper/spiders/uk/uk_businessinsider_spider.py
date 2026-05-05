import scrapy
import json
import re
from datetime import datetime
from news_scraper.spiders.smart_spider import SmartSpider


class UkBusinessinsiderSpider(SmartSpider):
    name = "uk_businessinsider"
    source_timezone = 'Europe/London'

    country_code = 'GBR'
    country = '英国'
    language = 'en'
    allowed_domains = ["businessinsider.com"]

    # No dates available on listing/AJAX pages; date extracted from JSON-LD in detail
    strict_date_required = False
    fallback_content_selector = "section.post-content, section.post-body-content, article"

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

    async def start(self):
        yield scrapy.Request(
            "https://www.businessinsider.com/economy",
            callback=self.parse_listing,
            dont_filter=True
        )

    def parse_listing(self, response):
        """Parse initial listing page and extract article links + pagination token."""
        article_links = response.css(
            'a.tout-title-link::attr(href), a.tout-image::attr(href)'
        ).getall()
        has_valid_item_in_window = False
        for link in list(set(article_links)):
            if self.should_process(link):
                has_valid_item_in_window = True
                yield response.follow(link, self.parse_detail)

        # Always start AJAX pagination from the initial page
        next_url_attr = response.css(
            'div[data-feed-id="economy"]::attr(data-next)'
        ).get()
        if next_url_attr:
            token_match = re.search(r'riverNextPageToken=([^&]+)', next_url_attr)
            if token_match:
                yield self.make_ajax_request(token_match.group(1))

    def make_ajax_request(self, token):
        ajax_url = (
            f"https://www.businessinsider.com/ajax/content-api/vertical"
            f"?templateId=legacy-river&capiVer=2&id=economy"
            f"&riverSize=50&riverNextPageToken={token}&page[limit]=20"
        )
        return scrapy.Request(
            ajax_url, callback=self.parse_ajax, meta={'token': token}
        )

    def parse_ajax(self, response):
        """Parse AJAX response for more article links with circuit breaker."""
        has_valid_item_in_window = False
        try:
            data = json.loads(response.text)
            html_snippet = data.get('rendered', '')
            if html_snippet:
                sel = scrapy.Selector(text=html_snippet)
                links = sel.css('a::attr(href)').getall()
                for link in list(set(links)):
                    if '/202' in link or '/201' in link:
                        if self.should_process(link):
                            has_valid_item_in_window = True
                            yield response.follow(link, self.parse_detail)

            if has_valid_item_in_window:
                next_token = None
                next_link = data.get('links', {}).get('next', '')
                if next_link:
                    token_match = re.search(
                        r'riverNextPageToken=([^&]+)', next_link
                    )
                    if token_match:
                        next_token = token_match.group(1)
                if next_token:
                    yield self.make_ajax_request(next_token)
        except Exception as e:
            self.logger.error(f"Failed to parse AJAX response: {e}")

    def parse_detail(self, response):
        """Parse article detail page with JSON-LD date extraction."""
        # Extract publish_time from JSON-LD (auto_parse_item doesn't handle JSON-LD)
        pub_date = None
        json_ld = response.xpath(
            '//script[@type="application/ld+json"]/text()'
        ).getall()
        for ld in json_ld:
            try:
                data = json.loads(ld)
                if isinstance(data, list):
                    for obj in data:
                        if 'datePublished' in obj:
                            d_str = obj['datePublished'].split('.')[0].replace('Z', '')
                            pub_date = datetime.fromisoformat(d_str)
                            break
                elif 'datePublished' in data:
                    d_str = data['datePublished'].split('.')[0].replace('Z', '')
                    pub_date = datetime.fromisoformat(d_str)
            except Exception:
                continue
            if pub_date:
                break

        if pub_date and not self.should_process(response.url, pub_date):
            return

        item = self.auto_parse_item(response)

        if pub_date:
            item['publish_time'] = self.parse_to_utc(pub_date)

        # Override title from manual extraction (cleaner than ContentEngine for this site)
        title = "".join(response.css('h1 *::text, .headline *::text').getall()).strip()
        if title:
            item['title'] = title

        # ContentEngine fallback: if it returned empty, try the broad container scan
        if not item.get('content_plain'):
            content_parts = response.css(
                'section.post-content p *::text, section.post-body-content p *::text, '
                'article p *::text, div.content-lock-content p *::text, '
                'section.post-body p *::text, .post-body-content *::text'
            ).getall()
            cleaned_content = "\n\n".join(
                [p.strip() for p in content_parts if len(p.strip()) > 10]
            )
            if cleaned_content:
                item['content_plain'] = cleaned_content

        item['author'] = "Business Insider"
        item['section'] = "Economy"

        if item.get('content_plain') and title:
            yield item
