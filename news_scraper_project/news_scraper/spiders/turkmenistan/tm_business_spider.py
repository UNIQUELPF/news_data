import scrapy
from news_scraper.spiders.smart_spider import SmartSpider


class TmBusinessSpider(SmartSpider):
    name = "tm_business"
    source_timezone = 'Asia/Ashgabat'

    country_code = 'TKM'
    country = '土库曼斯坦'
    language = 'en'

    allowed_domains = ['business.com.tm']

    # URL for pagination containing the explicit API index
    base_url = 'https://business.com.tm/post/a/index?path=news&Post_sort=date_added.desc&page={}'

    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'CONCURRENT_REQUESTS': 8,
        'DOWNLOAD_DELAY': 1,
        'ROBOTSTXT_OBEY': False,
    }

    use_curl_cffi = True
    strict_date_required = True
    fallback_content_selector = "div.content"

    async def start(self):
        """Initial requests entry point."""
        yield scrapy.Request(self.base_url.format(1), callback=self.parse, dont_filter=True)

    def parse(self, response):
        """
        Parse listing page: extract article links and paginate.
        Note: No date info available on this listing page, so circuit breaker
        only checks link presence. Date filtering happens in parse_article.
        """
        # Extract article links
        links = response.css('h4.entry-title a::attr(href)').getall()
        # Fallback if the layout changes: any link with /post/[id]/[slug]
        if not links:
            links = response.css('a[href*="/post/"]::attr(href)').getall()

        valid_links = []
        for link in set(links):
            # Check if it looks like an article detail link: /post/\d+/.*
            parts = link.split('/post/')
            if len(parts) > 1 and parts[1].split('/')[0].isdigit():
                valid_links.append(link)

        has_valid_item_in_window = False

        for link in valid_links:
            has_valid_item_in_window = True
            yield response.follow(link, self.parse_article)

        # Pagination: continue as long as there are links on the page
        if has_valid_item_in_window:
            current_page = response.meta.get('page', 1)
            next_page = current_page + 1
            yield scrapy.Request(
                self.base_url.format(next_page),
                callback=self.parse,
                meta={'page': next_page}
            )

    def parse_article(self, response):
        """Parse article detail page using standardized SmartSpider extraction."""
        # Extract publish_time manually for should_process check
        publish_time = None
        datetime_str = response.css('time::attr(datetime)').get()
        if datetime_str:
            try:
                datetime_str = datetime_str.replace('Z', '+00:00')
                from datetime import datetime
                publish_time = datetime.fromisoformat(datetime_str)
                publish_time = self.parse_to_utc(publish_time)
            except Exception as e:
                self.logger.warning(f"Date parsing failed for {response.url}: {e} on string {datetime_str}")

        if not publish_time:
            # Fallback to meta tag
            meta_date = response.css('meta[property="article:published_time"]::attr(content)').get()
            if meta_date:
                try:
                    from datetime import datetime
                    publish_time = datetime.fromisoformat(meta_date.replace('Z', '+00:00'))
                    publish_time = self.parse_to_utc(publish_time)
                except Exception:
                    pass

        # Date and dedup filtering via SmartSpider's should_process
        if not self.should_process(response.url, publish_time):
            return

        # Standard SmartSpider auto extraction
        item = self.auto_parse_item(
            response,
            title_xpath="string(//h1)",
            publish_time_xpath="//time/@datetime"
        )

        # Override specific fields for this source
        item['author'] = 'Business.com.tm'
        item['section'] = 'News'

        yield item
