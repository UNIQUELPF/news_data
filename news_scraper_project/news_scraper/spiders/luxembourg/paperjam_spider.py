import json
import re

import scrapy
from news_scraper.spiders.smart_spider import SmartSpider


class PaperjamSpider(SmartSpider):
    name = "luxembourg_paperjam"

    country_code = 'LUX'
    country = '卢森堡'
    language = 'fr'
    source_timezone = 'Europe/Luxembourg'

    allowed_domains = ["paperjam.lu"]

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 0.5,
    }

    CATEGORIES = [
        'politique-institutions/politique',
        'politique-institutions/institutions',
        'politique-institutions/economie',
        'politique-institutions/justice',
        'politique-institutions/education',
        'politique-institutions/europe',
        'politique-institutions/monde',
        'place-financiere-marches/banques',
        'place-financiere-marches/fonds',
        'place-financiere-marches/assurances',
        'place-financiere-marches/wealth-management',
        'place-financiere-marches/private-equity',
        'place-financiere-marches/fintech',
        'place-financiere-marches/marches-financiers',
        'entreprises-strategies/finance-legal',
        'entreprises-strategies/services-conseils',
        'entreprises-strategies/technologies',
        'entreprises-strategies/industrie',
        'entreprises-strategies/immobilier',
        'entreprises-strategies/artisanat',
        'entreprises-strategies/commerce',
        'communautes-expertises/knowledge',
        'communautes-expertises/mouvements',
        'communautes-expertises/communiques-de-presse',
        'lifestyle-vie-pratique/foodzilla',
        'lifestyle-vie-pratique/foodzilla-guide',
        'lifestyle-vie-pratique/sorties',
        'lifestyle-vie-pratique/bien-etre',
        'lifestyle-vie-pratique/style',
        'lifestyle-vie-pratique/habitat',
        'lifestyle-vie-pratique/voyages',
        'lifestyle-vie-pratique/techno',
        'lifestyle-vie-pratique/drive',
        'lifestyle-vie-pratique/argent',
        'lifestyle-vie-pratique/carriere',
        'lifestyle-vie-pratique/mobilite',
        'lifestyle-vie-pratique/concours'
    ]

    def start_requests(self):
        for cat in self.CATEGORIES:
            url = f"https://paperjam.lu/sector/{cat}?page=1"
            yield scrapy.Request(
                url,
                callback=self.parse_list,
                meta={'cat': cat, 'page': 1},
                dont_filter=True
            )

    def find_articles(self, obj):
        """Recursively walk JSON to find article objects (those with slug + publicationDate)."""
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
            publish_time = self.parse_date(pub_date_str) if pub_date_str else None

            article_url = f"https://paperjam.lu/article/{item['slug']}"

            if not self.should_process(article_url, publish_time):
                continue

            has_valid_item_in_window = True

            yield scrapy.Request(
                article_url,
                callback=self.parse_article,
                meta={
                    'publish_time_hint': publish_time,
                },
                dont_filter=self.full_scan,
            )

        # Pagination
        if has_valid_item_in_window:
            pagination = sub_page.get('pagination', {})
            count = pagination.get('count', 0)
            offset = pagination.get('offset', 0)
            limit = pagination.get('limit', 16)

            if offset + limit < count:
                next_page = page + 1
                next_url = f"https://paperjam.lu/sector/{cat}?page={next_page}"
                yield scrapy.Request(
                    next_url,
                    callback=self.parse_list,
                    meta={'cat': cat, 'page': next_page},
                    dont_filter=True
                )
            else:
                self.logger.info(f"Reached end of pagination for {cat}")
        else:
            self.logger.info(f"No new articles in window for {cat} at page {page}")

    def extract_text(self, obj):
        """Recursively extract text fields from JSON content blocks."""
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
        # Extract metadata from __NEXT_DATA__ JSON for maximum accuracy
        match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', response.text)

        title_hint = None
        json_publish_time = None
        author_hint = None
        section_hint = "Unknown"
        json_content = None

        if match:
            try:
                data = json.loads(match.group(1))
                article = data.get('props', {}).get('pageProps', {}).get('data', {}).get('article')
                if article:
                    metadata = article.get('metadata', {})
                    title_hint = metadata.get('title')

                    pub_date_str = article.get('publication', {}).get('date') or metadata.get('creationDate')
                    if pub_date_str:
                        json_publish_time = self.parse_date(pub_date_str)

                    author_data = metadata.get('author')
                    if isinstance(author_data, dict):
                        author_hint = author_data.get('name', '')

                    top_cat = metadata.get('topCategory', {})
                    cat_sector = top_cat.get('sector', '')
                    cat_subsector = top_cat.get('subSector', '')
                    if cat_sector:
                        section_hint = f"{cat_sector}/{cat_subsector}"

                    # Extract content from JSON as fallback
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

                    if paragraphs:
                        json_content = "\n\n".join(paragraphs)
            except (json.JSONDecodeError, Exception):
                pass

        # Use JSON publish time if list page didn't provide one
        if not response.meta.get('publish_time_hint') and json_publish_time:
            response.meta['publish_time_hint'] = json_publish_time

        item = self.auto_parse_item(response)

        # Override with JSON-extracted metadata (more accurate than ContentEngine guesses)
        if title_hint:
            item['title'] = title_hint

        # Use JSON-extracted time as authoritative
        publish_time = response.meta.get('publish_time_hint') or json_publish_time
        if publish_time:
            item['publish_time'] = publish_time

        if author_hint:
            item['author'] = author_hint

        item['section'] = section_hint

        # If ContentEngine didn't extract meaningful content, fall back to JSON content
        content_plain = item.get('content_plain', '') or ''
        if (not content_plain or len(content_plain) < 100) and json_content:
            item['content_plain'] = json_content

        yield item
