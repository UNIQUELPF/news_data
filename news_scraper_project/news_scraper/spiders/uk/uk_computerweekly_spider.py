import scrapy
import re
from datetime import datetime
from news_scraper.spiders.smart_spider import SmartSpider


class UkComputerweeklySpider(SmartSpider):
    name = "uk_computerweekly"
    source_timezone = 'Europe/London'

    country_code = 'GBR'
    country = '英国'
    language = 'en'
    allowed_domains = ["computerweekly.com", "r.jina.ai"]

    # No listing page; single URL mode via target_url.
    # Dates may not always be extractable from Jina response, so relax strict mode
    # to match original behavior where absent date did not block yield.
    strict_date_required = False
    fallback_content_selector = "article"

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "news_scraper.middlewares.CurlCffiMiddleware": 543,
            "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
        },
        "CURLL_CFFI_IMPERSONATE": "chrome120",
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0
    }

    use_curl_cffi = True

    def __init__(self, target_url=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.target_url = target_url

    async def start(self):
        if self.target_url:
            jina_url = f"https://r.jina.ai/{self.target_url}"
            yield scrapy.Request(
                jina_url,
                callback=self.parse_jina,
                meta={"original_url": self.target_url}
            )

    def parse_jina(self, response):
        """Parse Jina.ai markdown response for article content."""
        body = response.text
        has_valid_item_in_window = False

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
                text_date = re.search(
                    r'([0-9]{1,2}\s+[A-Z][a-z]{2,9}\s+2026)', body
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

        has_valid_item_in_window = True

        # 3. Content
        content_split = body.split("Markdown Content:")
        content = ""
        if len(content_split) > 1:
            content = content_split[1].strip()
            content = re.sub(r'!\[.*?\]\(.*?\)', '', content)
            content = re.sub(r'\n{3,}', '\n\n', content)

        if title and content:
            yield {
                "url": url,
                "title": title,
                "content_plain": content,
                "publish_time": pub_date,
                "author": "Computer Weekly",
                "language": "en",
                "section": "IT News",
                "raw_html": response.text,
            }
