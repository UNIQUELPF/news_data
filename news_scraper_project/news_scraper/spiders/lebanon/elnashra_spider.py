from datetime import datetime, timezone

import scrapy
from bs4 import BeautifulSoup
from news_scraper.spiders.smart_spider import SmartSpider


class ElnashraSpider(SmartSpider):
    """
    Spider for Elnashra (www.elnashra.com) - Lebanon Important News.
    Pagination relies on URL query params `ajax=1&timestamp=LAST_TIMESTAMP&page=NEXT_PAGE`.
    """
    name = "lebanon_elnashra"

    country_code = 'LBN'
    country = '黎巴嫩'
    language = 'ar'
    source_timezone = 'Asia/Beirut'

    use_curl_cffi = True
    # .articleBody is the primary container; .news_body / .newscontainer
    # are broader wrappers that also contain <p> article text.
    fallback_content_selector = '.articleBody, .news_body, .newscontainer'

    allowed_domains = ["elnashra.com"]


    base_list_url = (
        "https://www.elnashra.com/category/show/important/news/"
        "%D8%A3%D8%AE%D8%A8%D8%A7%D8%B1-%D9%85%D9%87%D9%85%D9%91%D8%A9"
    )

    custom_settings = {
        "DOWNLOAD_DELAY": 0.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 5,
        "RANDOMIZE_DOWNLOAD_DELAY": True,
        "DOWNLOAD_FAIL_ON_DATALOSS": False,
    }

    async def start(self):
        yield scrapy.Request(
            url=self.base_list_url,
            callback=self.parse,
            meta={'page_num': 1},
        dont_filter=True,
        )

    def parse(self, response):
        meta = response.meta
        page_num = meta.get('page_num', 1)

        news_items = response.css('li.newsfeed-main:not(.adWrapper)')
        if not news_items:
            self.logger.info("No news items found on list page.")
            return

        self.logger.info(
            f"Loaded list page {page_num} with {len(news_items)} items. URL: {response.url}"
        )

        has_valid_item_in_window = False
        last_timestamp = None

        for item in news_items:
            ts_str = item.xpath('@data-timestamp').get()
            if not ts_str:
                continue

            last_timestamp = ts_str
            # Unix timestamp -> naive UTC
            pub_time_utc = datetime.fromtimestamp(
                int(ts_str), tz=timezone.utc
            ).replace(tzinfo=None)

            a_tag = item.css('a:not(.notarget)')
            if not a_tag:
                a_tag = item.css('a')

            url = a_tag.xpath('@href').get()
            title = a_tag.xpath('@title').get()

            if not title:
                title = (
                    item.css('h2.topTitle::text').get()
                    or item.css('h3::text').get()
                    or "No Title"
                )

            title = title.strip()

            if not url:
                continue

            url = response.urljoin(url)

            if not self.should_process(url, pub_time_utc):
                continue

            has_valid_item_in_window = True

            yield scrapy.Request(
                url,
                callback=self.parse_article,
                meta={
                    'publish_time_hint': pub_time_utc,
                    'title_hint': title,
                },
                dont_filter=True,
            )

        if has_valid_item_in_window and last_timestamp:
            next_page = page_num + 1
            next_url = (
                f"{self.base_list_url}"
                f"?ajax=1&timestamp={last_timestamp}&page={next_page}"
            )
            yield scrapy.Request(
                next_url,
                callback=self.parse,
                meta={'page_num': next_page},
                dont_filter=True,
            )

    def _extract_content(self, response):
        """Extract article content via BS4 directly.

        The site's Arabic content is often stripped by trafilatura's text-density heuristics.
        BS4 direct extraction preserves all paragraphs.

        Tries multiple selectors in order so a template change or partial redirect does not
        cause the spider to fall through to trafilatura (which strips Arabic).
        """
        soup = BeautifulSoup(response.text, 'html.parser')
        selectors = ['.boxescontainer', '.articleBody', '.news_body', '.newscontainer', '.body_container']
        body = None
        for sel in selectors:
            candidate = soup.select_one(sel)
            if candidate:
                body = candidate
                break
        if not body:
            return ''

        for tag in body.find_all(['script', 'style', 'nav', 'footer', 'aside']):
            tag.decompose()

        parts = []
        for node in body.find_all(['p', 'h2', 'h3', 'li']):
            text = node.get_text(strip=True)
            if text:
                parts.append(text)
        return '\n\n'.join(parts)

    def parse_article(self, response):
        content = self._extract_content(response)

        # Always use _extract_content() if it returned anything.
        # ContentEngine strips Arabic, so we must NOT fall back to auto_parse_item
        # unless BS4 extraction returned empty.
        if content:
            title = (response.css('h1.topTitle::text').get()
                     or response.css('title::text').get()
                     or response.meta.get('title_hint', '')).strip()

            meta_image = response.xpath("//meta[@property='og:image']/@content").get()
            images = [response.urljoin(meta_image)] if meta_image else []

            publish_time = response.meta.get('publish_time_hint')

            item = {
                'url': response.url,
                'title': title,
                'content_plain': content,
                'content_html': f'<div class="article-content">{content}</div>',
                'publish_time': publish_time,
                'images': images,
                'raw_html': response.text,
                'language': self.language,
                'section': 'Important News',
                'country_code': self.country_code,
                'country': self.country,
            }
            item['author'] = 'Elnashra'
        else:
            item = self.auto_parse_item(
                response,
                title_xpath="//h1[@class='topTitle']//text()",
            )
            # Detail page h1 title is preferred over listing title (original behavior)
            detail_title = response.css('h1.topTitle::text').get()
            if detail_title:
                item['title'] = detail_title.strip()
            item['author'] = 'Elnashra'
            item['section'] = 'Important News'

        yield item
