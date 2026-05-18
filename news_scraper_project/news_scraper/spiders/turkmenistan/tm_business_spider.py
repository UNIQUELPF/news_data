import scrapy
from news_scraper.spiders.smart_spider import SmartSpider


class TmBusinessSpider(SmartSpider):
    name = "tm_business"
    source_timezone = 'Asia/Ashgabat'

    country_code = 'TKM'
    country = '土库曼斯坦'
    language = 'en'
    dateparser_settings = {"DATE_ORDER": "DMY"}

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
    fallback_content_selector = "div#printdiv .article_text"

    async def start(self):
        """Initial requests entry point."""
        yield scrapy.Request(self.base_url.format(1), callback=self.parse, dont_filter=True)

    def parse(self, response):
        """
        Parse listing page: extract article links and paginate.
        """
        # Extract article links
        links = response.css('h4.entry-title a::attr(href), div.entry-title a::attr(href)').getall()
        # Fallback if the layout changes
        if not links:
            links = response.css('a[href*="/post/"]::attr(href)').getall()

        valid_links = []
        for link in set(links):
            # Check if it looks like an article detail link: /post/\d+/.*
            parts = link.split('/post/')
            if len(parts) > 1 and parts[1].split('/')[0].isdigit():
                valid_links.append(link)

        for link in valid_links:
            yield response.follow(link, self.parse_article)

        # Pagination
        current_page = response.meta.get('page', 1)
        if current_page < 5: # Limit to 5 pages for debug
            next_page = current_page + 1
            yield scrapy.Request(
                self.base_url.format(next_page),
                callback=self.parse,
                meta={'page': next_page},
                dont_filter=True
            )

    def parse_article(self, response):
        """Parse article detail page using standardized SmartSpider extraction."""
        # Extract publish_time manually for debugging
        publish_time = None
        datetime_str = response.css('time::attr(datetime)').get()
        self.logger.info(f"DEBUG DATE: URL={response.url} STR={datetime_str}")
        
        if datetime_str:
            try:
                from datetime import datetime
                # Try multiple formats
                if 'T' in datetime_str:
                    publish_time = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
                elif '.' in datetime_str:
                    clean_str = datetime_str.split('+')[0].strip()
                    if ':' in clean_str:
                        publish_time = datetime.strptime(clean_str, '%d.%m.%Y %H:%M:%S')
                    else:
                        publish_time = datetime.strptime(clean_str, '%d.%m.%Y')
                
                if publish_time:
                    publish_time = self.parse_to_utc(publish_time)
            except Exception as e:
                self.logger.warning(f"Date parsing failed for {response.url}: {e}")

        # Standard SmartSpider auto extraction
        item = self.auto_parse_item(
            response,
            title_xpath="string(//h1)",
            publish_time_xpath="//time/@datetime"
        )
        if publish_time:
            item['publish_time'] = publish_time

        # Override specific fields for this source
        item['author'] = 'Business.com.tm'
        item['section'] = 'News'

        yield item
