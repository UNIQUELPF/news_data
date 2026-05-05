import scrapy
import re
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
    fallback_content_selector = None  # Jina handles content

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

    def parse_article(self, response):
        """Parse Jina.ai markdown response for article content."""
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

        if title and content:
            section = "Commons" if "commons-news" in url else "Lords"
            if "committee" in url:
                section = "Committees"

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
