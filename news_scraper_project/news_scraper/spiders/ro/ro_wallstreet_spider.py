import scrapy
import re
from datetime import datetime
from bs4 import BeautifulSoup
from news_scraper.spiders.smart_spider import SmartSpider


class RoWallstreetSpider(SmartSpider):
    name = "ro_wallstreet"
    country_code = 'ROU'
    country = '罗马尼亚'
    language = 'ro'
    source_timezone = 'Europe/Bucharest'
    allowed_domains = ["www.wall-street.ro"]
    fallback_content_selector = '.article-content, article, main'

    use_curl_cffi = True
    strict_date_required = False

    # Romanian months mapping (abbreviated/full)
    MONTHS_RO = {
        "ian.": 1, "ianuarie": 1,
        "feb.": 2, "februarie": 2,
        "mar.": 3, "martie": 3,
        "apr.": 4, "aprilie": 4,
        "mai": 5,
        "iun.": 6, "iunie": 6,
        "iul.": 7, "iulie": 7,
        "aug.": 8, "august": 8,
        "sep.": 9, "septembrie": 9,
        "oct.": 10, "octombrie": 10,
        "noi.": 11, "noiembrie": 11,
        "dec.": 12, "decembrie": 12
    }

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "news_scraper.middlewares.CurlCffiMiddleware": 543,
            "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
        },
        "CURLL_CFFI_IMPERSONATE": "chrome120",
        "CONCURRENT_REQUESTS": 8,
        "DOWNLOAD_DELAY": 0.5,
    }

    async def start(self):
        yield scrapy.Request(
            "https://www.wall-street.ro/articol/economie-and-finante/index.html",
            callback=self.parse,
        dont_filter=True,
        )

    def parse(self, response):
        articles = response.css('a.article-wrapper')
        has_valid_item_in_window = False

        for article in articles:
            link = article.css('::attr(href)').get()
            if not link:
                continue

            if not link.startswith('http'):
                link = "https://www.wall-street.ro" + link

            title = article.css('h4::text').get()
            
            # Try to extract date from the card text
            card_text = " ".join(article.css('*::text').getall())
            pub_date = self._parse_ro_date(card_text)

            if self.should_process(link, pub_date):
                has_valid_item_in_window = True
                yield scrapy.Request(
                    link,
                    callback=self.parse_article,
                    meta={'title_hint': title, 'pub_date': pub_date}
                )

        if has_valid_item_in_window and not getattr(self, 'has_hit_date_limit', False):
            current_page = 1
            if '?page=' in response.url:
                try:
                    match = re.search(r'page=(\d+)', response.url)
                    if match:
                        current_page = int(match.group(1))
                except:
                    pass

            next_page_url = f"https://www.wall-street.ro/articol/economie-and-finante/index.html?page={current_page + 1}"
            yield scrapy.Request(next_page_url, callback=self.parse)

    def _extract_content(self, response):
        """Extract article content via CSS selectors (ContentEngine/trafilatura misses this site).

        DOM structure observed:
          article > .article-section > section > .article-content.main-container
        The plain .article-content selector only matches the ~200-char intro paragraph,
        not the full body. We target the main section/article instead.
        """
        soup = BeautifulSoup(response.text, 'html.parser')
        # Try the main content area inside article, from most to least specific
        root_el = (soup.select_one('article > .article-section > section')
                   or soup.select_one('.article-content.main-container')
                   or soup.select_one('.article-section')
                   or soup.select_one('article')
                   or soup.select_one('main'))
        if not root_el:
            return ''
        for t in root_el(['script', 'style', 'nav', 'footer', 'aside']):
            t.decompose()
        parts = []
        for node in root_el.find_all(['p', 'h2', 'h3', 'li']):
            text = node.get_text(strip=True)
            if text and len(text) > 20:
                parts.append(text)
        return '\n\n'.join(parts)

    def _parse_ro_date(self, date_str):
        if not date_str:
            return None
        try:
            date_str = date_str.strip().lower()
            match = re.search(r'(\d{1,2})\s+([a-z\.]+)\s+(\d{4})', date_str)
            if match:
                day = int(match.group(1))
                month_name = match.group(2).strip('.')
                year = int(match.group(3))

                if month_name in self.MONTHS_RO:
                    month = self.MONTHS_RO[month_name]
                elif (month_name + '.') in self.MONTHS_RO:
                    month = self.MONTHS_RO[month_name + '.']
                else:
                    month = None

                if month:
                    pub_date = datetime(year, month, day)
                    return self.parse_to_utc(pub_date)
        except Exception:
            pass
        return None

    def parse_article(self, response):
        # Retrieve parsed date from list page, or try parsing from article page
        pub_date = response.meta.get('pub_date')
        if not pub_date:
            date_str = response.css('.article-meta .date::text').get()
            pub_date = self._parse_ro_date(date_str)

        # Direct content extraction via CSS selector (ContentEngine/trafilatura misses this site)
        content = self._extract_content(response)

        if content:
            title = (response.css('h1::text').get()
                     or response.css('title::text').get()
                     or response.meta.get('title_hint', '')).strip()

            meta_image = response.xpath("//meta[@property='og:image']/@content").get()
            images = [response.urljoin(meta_image)] if meta_image else []

            item = {
                'url': response.url,
                'title': title,
                'content_plain': content,
                'content_html': f'<div class="article-content">{content}</div>',
                'publish_time': pub_date,
                'images': images,
                'raw_html': response.text,
                'language': self.language,
                'section': 'Economy',
                'country_code': self.country_code,
                'country': self.country,
            }
        else:
            # Fall back to ContentEngine auto_parse_item
            item = self.auto_parse_item(response)

        item['publish_time'] = pub_date or item.get('publish_time')
        item['author'] = 'Wall-Street.ro'
        item['section'] = 'Economy'

        if not self.should_process(response.url, item.get('publish_time')):
            self.has_hit_date_limit = True
            return

        if item.get('content_plain') and len(item['content_plain']) > 50:
            yield item
