import json
import logging
import re

import dateparser
import scrapy
from news_scraper.spiders.smart_spider import SmartSpider

logger = logging.getLogger(__name__)


class DelanoSpider(SmartSpider):
    name = "luxembourg_delano"
    source_timezone = 'Europe/Luxembourg'

    country_code = 'LUX'
    country = '卢森堡'
    language = 'en'
    start_date = '2026-01-01'

    allowed_domains = ["delano.lu"]

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 0.5,
    }

    CATEGORIES = [
        'community-expertise/career-moves',
        'community-expertise/communication',
        'community-expertise/financial-place',
        'community-expertise/hr',
        'community-expertise/legal',
        'community-expertise/press-release',
        'community-expertise/real-estate',
        'companies-strategies/architecture-real-estate',
        'companies-strategies/finance-legal',
        'companies-strategies/industry',
        'companies-strategies/retail',
        'companies-strategies/services-advisory',
        'companies-strategies/technology',
        'companies-strategies/trades',
        'finance/banks',
        'finance/fintech',
        'finance/funds',
        'finance/insurance',
        'finance/markets',
        'finance/private-equity',
        'finance/wealth-management',
        'lifestyle/careers',
        'lifestyle/competitions',
        'lifestyle/culture',
        'lifestyle/drive',
        'lifestyle/expat-guide',
        'lifestyle/foodzilla',
        'lifestyle/foodzilla-guide',
        'lifestyle/home',
        'lifestyle/money',
        'lifestyle/personal-tech',
        'lifestyle/sports-wellbeing',
        'lifestyle/style',
        'lifestyle/transport',
        'lifestyle/travel',
        'politics-institutions/economy',
        'politics-institutions/education',
        'politics-institutions/europe',
        'politics-institutions/institutions',
        'politics-institutions/justice',
        'politics-institutions/politics',
        'politics-institutions/world'
    ]

    async def start(self):
        for cat in self.CATEGORIES:
            url = f"https://delano.lu/sector/{cat}?page=1"
            yield scrapy.Request(url, callback=self.parse_list, dont_filter=True, meta={'cat': cat, 'page': 1})

    def find_articles(self, obj):
        found = []
        if isinstance(obj, dict):
            if 'slug' in obj and 'publicationDate' in obj:
                found.append(obj)
            for v in obj.values():
                found.extend(self.find_articles(v))
        elif isinstance(obj, list):
            for item in obj:
                found.extend(self.find_articles(item))
        return found

    def parse_list(self, response):
        cat = response.meta['cat']
        page = response.meta['page']

        match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', response.text)
        if not match:
            self.logger.error(f"Failed to find __NEXT_DATA__ on {response.url}")
            return

        data = json.loads(match.group(1))
        sub_page = data.get('props', {}).get('pageProps', {}).get('data', {}).get('subSectorPage', {})
        articles_data = sub_page.get('articles', {})

        if not articles_data:
            self.logger.info(f"No articles mapped on {response.url}")
            return

        all_slugs = set()
        article_items = []

        extracted = self.find_articles(articles_data)
        for item in extracted:
            slug = item.get('slug')
            if slug and slug not in all_slugs:
                all_slugs.add(slug)
                article_items.append(item)

        if not article_items:
            return

        has_valid_item_in_window = False

        for item in article_items:
            pub_date_str = item.get('publicationDate')
            if not pub_date_str:
                continue

            dt = dateparser.parse(pub_date_str)
            if not dt:
                continue

            publish_time = self.parse_to_utc(dt)
            article_url = f"https://delano.lu/article/{item['slug']}"

            if not self.should_process(article_url, publish_time):
                continue

            has_valid_item_in_window = True
            self.logger.info(f"Processing: {article_url} ({pub_date_str})")

            yield scrapy.Request(
                article_url,
                callback=self.parse_article,
                dont_filter=self.full_scan,
                meta={
                    'publish_time_hint': publish_time,
                    'section_hint': cat,
                }
            )

        # Pagination with circuit breaker
        if has_valid_item_in_window:
            pagination = sub_page.get('pagination', {})
            count = pagination.get('count', 0)
            offset = pagination.get('offset', 0)
            limit = pagination.get('limit', 16)

            if offset + limit < count:
                next_page = page + 1
                next_url = f"https://delano.lu/sector/{cat}?page={next_page}"
                yield scrapy.Request(
                    next_url,
                    callback=self.parse_list,
                    dont_filter=True,
                    meta={'cat': cat, 'page': next_page}
                )
            else:
                self.logger.info(f"Reached end of pagination for {cat}")
        else:
            self.logger.info(f"No valid items in window for {cat} at page {page}")

    def extract_text(self, obj):
        text = ""
        if isinstance(obj, dict):
            if 'text' in obj and isinstance(obj['text'], str):
                text += obj['text']
            for k, v in obj.items():
                if k != 'text':
                    text += self.extract_text(v)
        elif isinstance(obj, list):
            for item in obj:
                text += self.extract_text(item)
        return text

    def parse_article(self, response):
        match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', response.text)
        if not match:
            return

        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            return

        article = data.get('props', {}).get('pageProps', {}).get('data', {}).get('article')
        if not article:
            return

        metadata = article.get('metadata', {})
        title = metadata.get('title', '')
        if not title:
            return

        pub_date_str = article.get('publication', {}).get('date') or metadata.get('creationDate')
        if not pub_date_str:
            return

        dt = dateparser.parse(pub_date_str)
        if not dt:
            return

        publish_time = self.parse_to_utc(dt)

        # V2: should_process as safety net (date may differ from list page)
        if not self.should_process(response.url, publish_time):
            return

        author_data = metadata.get('author')
        author = author_data.get('name') if isinstance(author_data, dict) else ""

        top_cat = metadata.get('topCategory', {})
        cat_sector = top_cat.get('sector', '')
        cat_subsector = top_cat.get('subSector', '')
        category = f"{cat_sector}/{cat_subsector}" if cat_sector else "Unknown"

        content_dict = article.get('content', {})
        paragraphs = []

        intro = content_dict.get('introduction')
        if intro:
            intro_text = self.extract_text(intro).strip()
            if intro_text:
                paragraphs.append(intro_text)

        body = content_dict.get('bodyContents')
        if isinstance(body, list):
            for block in body:
                if isinstance(block, list) and len(block) == 2:
                    block_text = self.extract_text(block[1])
                    block_text = re.sub(r'\s+', ' ', block_text).strip()
                    if block_text:
                        paragraphs.append(block_text)

        content_text = "\n\n".join(paragraphs)
        if not content_text:
            self.logger.warning(f"No content found for: {response.url}")
            return

        yield {
            'url': response.url,
            'title': title,
            'publish_time': publish_time,
            'author': author,
            'content_plain': content_text,
            'raw_html': response.text,
            'language': 'en',
            'section': category,
            'country_code': 'LUX',
            'country': '卢森堡',
        }
