import scrapy
import re
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urljoin
from news_scraper.spiders.smart_spider import SmartSpider


class UkParliamentSpider(SmartSpider):
    name = "uk_parliament"
    source_timezone = 'Europe/London'

    country_code = 'GBR'
    country = '英国'
    language = 'en'
    allowed_domains = ["parliament.uk", "r.jina.ai"]

    # No dates on listing cards; dates extracted from Jina response in detail
    strict_date_required = False
    # Jina handles content; fallback used when Jina returns too little
    fallback_content_selector = "article, [role='main'], main, .content, #content"

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "news_scraper.middlewares.CurlCffiMiddleware": 543,
            "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
        },
        "CURLL_CFFI_IMPERSONATE": "chrome120",
        "CONCURRENT_REQUESTS": 4,
        "DOWNLOAD_DELAY": 1.0
    }

    use_curl_cffi = True

    MIN_JINA_CONTENT_LENGTH = 500

    async def start(self):
        yield scrapy.Request(
            "https://www.parliament.uk/business/news/parliament-government-and-politics/parliament/commons-news/?page=1",
            callback=self.parse_listing,
            dont_filter=True
        )
        yield scrapy.Request(
            "https://www.parliament.uk/business/news/parliament-government-and-politics/parliament/lords-news/?page=1",
            callback=self.parse_listing,
            dont_filter=True
        )

    def parse_listing(self, response):
        """Parse listing page with cards and pagination circuit breaker."""
        cards = response.css('a.card.card-content')
        if not cards:
            self.logger.info(f"No cards found on {response.url}")
            return

        has_valid_item_in_window = False
        for card in cards:
            link = card.attrib.get('href')
            if not link:
                continue
            full_url = urljoin(response.url, link)

            if not self.should_process(full_url):
                continue

            has_valid_item_in_window = True
            jina_url = f"https://r.jina.ai/{full_url}"
            yield scrapy.Request(
                jina_url,
                callback=self.parse_article,
                meta={"original_url": full_url}
            )

        # Pagination with circuit breaker
        if has_valid_item_in_window:
            current_page = 1
            match = re.search(r'page=(\d+)', response.url)
            if match:
                current_page = int(match.group(1))

            next_page = current_page + 1
            next_url = re.sub(
                r'page=\d+', f'page={next_page}', response.url
            )
            yield scrapy.Request(
                next_url, callback=self.parse_listing
                )

    def _extract_content(self, response):
        """Extract article content directly from a Parliament UK HTML page
        using bs4. Used as fallback when Jina.ai returns too little content.
        """
        soup = BeautifulSoup(response.text, 'lxml')

        # --- Title ---
        title = None
        og_title = soup.select_one('meta[property="og:title"]')
        if og_title:
            title = og_title.get('content', '').strip()

        if not title:
            h1 = soup.select_one('h1')
            if h1:
                title = h1.get_text(strip=True)

        # --- Content ---
        # Try several common containers for UK Parliament / GOV.UK-style pages
        content_area = (
            soup.select_one('article[role="main"]')
            or soup.select_one('main')
            or soup.select_one('[role="main"]')
            or soup.select_one('.content')
            or soup.select_one('#content')
            or soup.select_one('article')
        )

        if not content_area:
            return None

        # Remove noise
        for tag in content_area.find_all(
            ['script', 'style', 'nav', 'footer', 'header', 'aside',
             'form', 'button', 'iframe']
        ):
            tag.decompose()

        # Get meaningful paragraph text
        paragraphs = content_area.find_all('p')
        content_plain = '\n\n'.join(
            p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)
        )

        if not content_plain or len(content_plain) < 50:
            content_plain = content_area.get_text(separator=' ', strip=True)

        if content_plain and len(content_plain) > 50:
            images = []
            for img in content_area.find_all('img'):
                src = img.get('src')
                if src:
                    alt = img.get('alt', '')
                    images.append({"url": urljoin(response.url, src), "alt": alt})

            return {
                "content_cleaned": str(content_area).strip(),
                "content_markdown": "",
                "content_plain": content_plain.strip(),
                "images": images,
                "title": title,
            }

        return None

    def parse_article(self, response):
        """Parse Jina.ai markdown response for article content.

        If Jina returns too little content (< MIN_JINA_CONTENT_LENGTH chars),
        fall back to fetching the original URL directly and extracting with
        bs4 via parse_article_direct.
        """
        body = response.text

        # 1. Title
        title_match = re.search(r'^Title:\s*(.*)$', body, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else ""

        # 2. Date
        date_match = re.search(r'^Published Time:\s*(.*)$', body, re.MULTILINE)
        pub_date = None
        if date_match:
            date_str = date_match.group(1).strip().split('+')[0].replace('Z', '')
            if len(date_str) == 16:
                date_str += ":00"
            try:
                pub_date = datetime.fromisoformat(date_str)
            except Exception:
                pass

        if not pub_date:
            text_date = re.search(
                r'([0-9]{1,2}\s+[A-Z][a-z]{2,8}\s+20[0-9]{2})', body
            )
            if text_date:
                try:
                    pub_date = datetime.strptime(
                        text_date.group(1), "%d %B %Y"
                    )
                except Exception:
                    pass

        url = response.meta["original_url"]
        if not self.should_process(url, pub_date):
            return

        # 3. Content
        content_split = body.split("Markdown Content:")
        content = ""
        if len(content_split) > 1:
            content = content_split[1].strip()
            content = re.sub(r'!\[.*?\]\(.*?\)', '', content)
            content = re.sub(r'\n{3,}', '\n\n', content)

        # 4. If Jina returned too little content, try direct extraction
        if len(content) < self.MIN_JINA_CONTENT_LENGTH:
            self.logger.info(
                f"Jina returned only {len(content)} chars for {url}; "
                f"falling back to direct extraction"
            )
            section = self._get_section(url)
            yield scrapy.Request(
                url,
                callback=self.parse_article_direct,
                meta={
                    "title": title,
                    "publish_time": pub_date,
                    "original_url": url,
                    "section": section,
                    "jina_content": content,
                },
                dont_filter=True,
            )
            return

        if title and content:
            section = self._get_section(url)

            yield {
                "url": url,
                "title": title,
                "content_plain": content,
                "publish_time": pub_date,
                "language": "en",
                "section": section,
                "author": "UK Parliament",
                "raw_html": response.text,
            }

    def _get_section(self, url):
        """Determine article section from URL."""
        if "committee" in url:
            return "Committees"
        return "Commons" if "commons-news" in url else "Lords"

    def parse_article_direct(self, response):
        """Fallback: extract content directly from Parliament article HTML.

        Triggered when Jina.ai returns too little content.  Uses the metadata
        already extracted from the Jina response (title, publish_time) and
        fills in the content via bs4 extraction of the raw HTML.
        """
        title = response.meta.get("title", "")
        pub_date = response.meta.get("publish_time")
        url = response.meta["original_url"]
        section = response.meta.get("section", "Lords")
        jina_content = response.meta.get("jina_content", "")

        content_data = self._extract_content(response)

        if content_data and content_data.get('content_plain') and len(content_data['content_plain']) > 50:
            self.logger.info(
                f"Direct extraction succeeded for {url}: "
                f"{len(content_data['content_plain'])} chars"
            )
            yield {
                "url": url,
                "title": title or content_data.get("title", ""),
                "content_plain": content_data["content_plain"],
                "publish_time": pub_date,
                "language": "en",
                "section": section,
                "author": "UK Parliament",
                "raw_html": response.text,
                "images": content_data.get("images", []),
            }
        else:
            # Both Jina and direct extraction failed; yield Jina's snippet
            self.logger.warning(
                f"Direct extraction also failed for {url}; yielding "
                f"{len(jina_content)} chars from Jina"
            )
            final_content = jina_content or response.text[:500]
            yield {
                "url": url,
                "title": title,
                "content_plain": final_content,
                "publish_time": pub_date,
                "language": "en",
                "section": section,
                "author": "UK Parliament",
                "raw_html": response.text,
            }
