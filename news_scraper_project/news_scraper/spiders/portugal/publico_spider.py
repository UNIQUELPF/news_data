import scrapy
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re
from news_scraper.spiders.smart_spider import SmartSpider


class PortugalPublicoSpider(SmartSpider):
    name = 'pt_publico'
    country_code = 'PRT'
    country = '葡萄牙'
    language = 'pt'
    source_timezone = 'Europe/Lisbon'
    start_date = '2024-01-01'
    allowed_domains = ['publico.pt']

    # The actual article body lives in .story__body / #story-body;
    # .story__content wraps header + body + footer.
    fallback_content_selector = '.story__content, #story-body, .story__body'

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.2,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 1,  # Serial: one-by-one detail check
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        }
    }

    async def start(self):
        base_url = 'https://www.publico.pt/economia'
        yield scrapy.Request(f"{base_url}?page=1", callback=self.parse_list, meta={'page': 1}, dont_filter=True)

    def parse_list(self, response):
        if self._stop_pagination:
            return

        articles = response.css('h2.headline a::attr(href)').getall() or \
                   response.css('h4.headline a::attr(href)').getall() or \
                   response.xpath('//a[contains(@href, "/noticia/")]/@href').getall()

        has_valid_item_in_window = False
        for link in articles:
            base_link = link.split('?')[0]
            full_url = response.urljoin(base_link)
            if '/202' in full_url and self.should_process(full_url):
                has_valid_item_in_window = True
                yield scrapy.Request(full_url, callback=self.parse_article)

        if has_valid_item_in_window:
            page = response.meta.get('page', 1)
            next_url = f"https://www.publico.pt/economia?page={page + 1}"
            yield scrapy.Request(next_url, callback=self.parse_list, meta={'page': page + 1}, dont_filter=True)

    def _extract_content(self, response):
        """Custom content extraction for Público article pages.

        Issues with the generic engine:
          - Title: //h1/text() hits the "Olá" greeting h1 first, not the article
                   h1.headline.story__headline.
          - Content: .story__content captures the paywall gate badly; the real
                     visible text is in .story__blurb.lead (lead) plus the
                     first paragraph(s) in #story-body.

        This method extracts title from og:title / h1.story__headline, and
        content from the lead + visible body paragraphs.
        """
        soup = BeautifulSoup(response.text, 'lxml')

        # --- Title ---
        title = None
        og_title = soup.select_one('meta[property="og:title"]')
        if og_title:
            title = og_title.get('content', '').strip()
            # Público og:title may contain " | EUA | PÚBLICO" suffix – keep it
            # since it carries disambiguation.

        if not title:
            h1 = soup.select_one('h1.headline.story__headline')
            if h1:
                title = h1.get_text(strip=True)

        if not title:
            # Last-resort: strip the site suffix if we caught a meta title
            candidate = (
                soup.select_one('meta[name="twitter:title"]')
            )
            if candidate:
                title = candidate.get('content', '').strip()

        # --- Content ---
        # Lead paragraph (always visible even behind paywall)
        lead_el = soup.select_one('.story__blurb.lead p')
        lead_text = lead_el.get_text(strip=True) if lead_el else ""

        # Visible body paragraphs (before paywall iframes)
        body_el = soup.select_one('#story-body') or soup.select_one('.story__body')
        visible_paragraphs = []
        if body_el:
            for child in body_el.children:
                # Stop at paywall / subscription iframes
                if child.name == 'iframe' or child.name == 'aside':
                    break
                if child.name == 'p' and child.get_text(strip=True):
                    visible_paragraphs.append(child.get_text(strip=True))

        parts = [lead_text] if lead_text else []
        parts.extend(visible_paragraphs)
        content_plain = '\n\n'.join(p for p in parts if p)

        if not content_plain or len(content_plain) < 50:
            # Fallback: try the whole story__content area
            content_el = soup.select_one('.story__content')
            if content_el:
                content_plain = content_el.get_text(separator=' ', strip=True)

        if content_plain and len(content_plain) > 30:
            images = []
            for img in soup.select('.story__content img, #story-body img, .story__body img'):
                src = img.get('src')
                if src:
                    alt = img.get('alt', '')
                    images.append({"url": urljoin(response.url, src), "alt": alt})

            return {
                "content_cleaned": "",
                "content_markdown": "",
                "content_plain": content_plain.strip(),
                "images": images,
                "title": title,
            }

        return None

    def parse_article(self, response):
        # Try custom extraction first (fixes title targeting + pays attention
        # to paywall boundary in body content).
        content_data = self._extract_content(response)
        if content_data and content_data.get('content_plain') and len(content_data['content_plain']) > 30:
            publish_time = None
            raw_time = response.xpath(
                "//meta[@property='article:published_time']/@content"
            ).get()
            if raw_time:
                import dateparser
                publish_time = self.parse_to_utc(dateparser.parse(raw_time))

            if not self.should_process(response.url, publish_time):
                self._stop_pagination = True
                return

            item = {
                **content_data,
                "url": response.url,
                "raw_html": response.text,
                "publish_time": publish_time,
                "language": self.language,
                "country_code": self.country_code,
                "country": self.country,
                "author": response.css('.story__author::text').get() or 'Público Portugal',
                "section": 'Economia',
            }
            yield item
        else:
            # Fall back to generic engine
            item = self.auto_parse_item(
                response,
                title_xpath="//h1/text()",
                publish_time_xpath="//meta[@property='article:published_time']/@content",
            )
            if not self.should_process(response.url, item.get('publish_time')):
                self._stop_pagination = True
                return
            item['author'] = response.css('.story__author::text').get() or 'Público Portugal'
            item['section'] = 'Economia'
            if item.get('content_plain') and len(item['content_plain']) > 50:
                yield item
