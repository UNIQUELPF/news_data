import html
import json
import re

import scrapy
from bs4 import BeautifulSoup
from news_scraper.spiders.smart_spider import SmartSpider


class GouvernementSpider(SmartSpider):
    name = "luxembourg_gouvernement"

    country_code = 'LUX'
    country = '卢森堡'
    language = 'fr'
    source_timezone = 'Europe/Luxembourg'

    allowed_domains = ["gouvernement.lu"]
    fallback_content_selector = "div.cmp-text"

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 0.5,
    }

    base_url = (
        "https://gouvernement.lu/content/gouvernement2024/fr/actualites/"
        "toutes_actualites/jcr:content/root/root-responsivegrid/"
        "content-responsivegrid/sections-responsivegrid/section/col1/"
        "search.searchresults-content.html?format=json&page={}"
    )

    async def start(self):
        yield scrapy.Request(
            self.base_url.format(1),
            callback=self.parse_list,
            meta={'page': 1},
            dont_filter=True
        )

    def parse_list(self, response):
        page = response.meta['page']

        match = re.search(r'data-json=\"(.*?)\"', response.text, re.DOTALL)
        if not match:
            self.logger.error(f"Failed to find data-json on {response.url}")
            return

        try:
            encoded_json = match.group(1)
            decoded_json = html.unescape(encoded_json)
            data = json.loads(decoded_json)
        except Exception as e:
            self.logger.error(f"Failed to parse JSON from {response.url}: {e}")
            return

        items = data.get('search', {}).get('items', [])
        if not items:
            self.logger.info(f"No items found on page {page}")
            return

        self.logger.info(f"Page {page}: found {len(items)} items")

        has_valid_item_in_window = False

        for item in items:
            page_data = item.get('page', {})
            title = page_data.get('title')
            url_rel = item.get('url')

            # Parse publish time (format: YYYY/MM/DD HH:MM:SS in Europe/Luxembourg)
            metadata = item.get('hitMetaData', {})
            pub_date_str = metadata.get('first_release_date_hour') or item.get('first_release_date_hour')

            if not pub_date_str:
                pub_date_str = item.get('startDateFormating', {}).get('fulltimeString')

            if not pub_date_str:
                self.logger.warning(f"Item missing publish date: {title}")
                continue

            publish_time = self.parse_date(pub_date_str)
            if not publish_time:
                self.logger.warning(f"Failed to parse date '{pub_date_str}': {title}")
                continue

            # Build full URL
            full_url = url_rel
            if full_url.startswith('//'):
                full_url = 'https:' + full_url
            elif full_url.startswith('/'):
                full_url = 'https://gouvernement.lu' + full_url

            if not self.should_process(full_url, publish_time):
                continue

            has_valid_item_in_window = True
            yield scrapy.Request(
                full_url,
                callback=self.parse_article,
                meta={
                    'title_hint': title,
                    'publish_time_hint': publish_time,
                    'section_hint': item.get('third_level', 'news'),
                }
            )

        if has_valid_item_in_window:
            next_page = page + 1
            yield scrapy.Request(
                self.base_url.format(next_page),
                callback=self.parse_list,
                meta={'page': next_page},
                dont_filter=True
            )
        else:
            self.logger.info(f"Reached cutoff or end of content at page {page}")

    def _extract_content(self, response):
        """Extract article content from all div.cmp-text blocks inside the main section.

        DOM structure:
          main > section.cmp-section (the second one, containing the article body)
            > div.cmp-section__content > div.aem-GridColumn > div.cmp-text (multiple)

        The default fallback 'div.cmp-text' only matches the first block (intro paragraph).
        We concatenate all cmp-text blocks for the full article.
        """
        soup = BeautifulSoup(response.text, 'html.parser')
        # Find all cmp-text blocks inside main
        text_blocks = soup.select('main div.cmp-text')
        if not text_blocks:
            return ''

        parts = []
        for block in text_blocks:
            for tag in block.find_all(['script', 'style']):
                tag.decompose()
            text = block.get_text(separator=' ', strip=True)
            if text:
                parts.append(text)

        return '\n\n'.join(parts)

    def parse_article(self, response):
        content = self._extract_content(response)

        if content and len(content) > 100:
            title = (response.css('h1::text').get()
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
                'section': response.meta.get('section_hint', 'news'),
                'country_code': self.country_code,
                'country': self.country,
            }
        else:
            item = self.auto_parse_item(response)

        item['author'] = ''
        yield item
