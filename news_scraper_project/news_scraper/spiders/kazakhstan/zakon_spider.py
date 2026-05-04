# 哈萨克斯坦zakon spider爬虫，负责抓取对应站点、机构或栏目内容。

import scrapy
from news_scraper.spiders.smart_spider import SmartSpider
from datetime import datetime, timedelta
import pytz
import re
from bs4 import BeautifulSoup
import asyncio

RU_MONTHS = {
    'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4,
    'мая': 5, 'июня': 6, 'июля': 7, 'августа': 8,
    'сентября': 9, 'октября': 10, 'ноября': 11, 'декабря': 12
}

class ZakonSpider(SmartSpider):
    name = 'zakon'

    country_code = 'KAZ'
    country = '哈萨克斯坦'
    language = 'ru'
    source_timezone = 'Asia/Almaty'
    start_date = '2024-01-01'

    allowed_domains = ['zakon.kz']
    start_urls = ['https://www.zakon.kz/finansy/']

    fallback_content_selector = 'div.content'

    custom_settings = {
        'PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT': 60000,
    }

    def parse_russian_date(self, date_str):
        """Converts Zakon.kz Russian date strings to naive UTC datetime objects."""
        almaty_tz = pytz.timezone('Asia/Almaty')
        now = datetime.now(almaty_tz)
        date_str = date_str.lower().strip()

        if "сегодня" in date_str:
            result = now.replace(hour=0, minute=0, second=0, microsecond=0)
            return self.parse_to_utc(result)

        if "вчера" in date_str:
            result = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            return self.parse_to_utc(result)

        match = re.search(r"(\d{1,2})\s+([а-я]+)(?:\s+(\d{4}))?", date_str)
        if match:
            day = int(match.group(1))
            month_str = match.group(2)
            year = int(match.group(3)) if match.group(3) else now.year

            month = RU_MONTHS.get(month_str)
            if month:
                result = datetime(year, month, day)
                return self.parse_to_utc(result)

        return None

    def start_requests(self):
        url = "https://www.zakon.kz/finansy/"
        yield scrapy.Request(
            url,
            meta={
                'playwright': True,
                'playwright_include_page': True,
                'playwright_page_goto_kwargs': {
                    'wait_until': 'domcontentloaded',
                    'timeout': 60000,
                }
            },
            callback=self.parse_list,
            dont_filter=self.full_scan,
        )

    async def parse_list(self, response):
        try:
            page = response.meta['playwright_page']
        except KeyError:
            self.logger.error("No playwright_page in meta")
            return

        stop_crawling = False
        seen_urls = set()
        attempts = 0

        while attempts < 50 and not stop_crawling:
            try:
                await page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
                await asyncio.sleep(2)

                cards_html = await page.content()
                soup = BeautifulSoup(cards_html, 'html.parser')
                links = soup.select('a.newscard_link')
                self.logger.debug(f"Found {len(links)} newscard_link elements")

                for link in links:
                    title_el = link.select_one('.newscard__title')
                    date_el = link.select_one('.newscard__dateline')

                    if not title_el or not date_el:
                        continue

                    title = title_el.get_text(strip=True)
                    date_str = date_el.get_text(strip=True)
                    href = link.get('href')
                    full_url = f"https://www.zakon.kz{href}" if href.startswith('/') else href

                    if full_url in seen_urls:
                        continue
                    seen_urls.add(full_url)

                    parsed_date = self.parse_russian_date(date_str)

                    if not self.should_process(full_url, parsed_date):
                        if parsed_date and self.cutoff_date and parsed_date < self.cutoff_date:
                            self.logger.info(f"Reached cutoff date: {parsed_date}. Stopping scroll.")
                            stop_crawling = True
                            break
                        continue

                    # Yield immediately while the Playwright page is alive
                    yield scrapy.Request(
                        full_url,
                        callback=self.parse_detail,
                        meta={
                            'title_hint': title,
                            'publish_time_hint': parsed_date,
                        },
                        dont_filter=self.full_scan,
                    )

                attempts += 1
                self.logger.info(f"Scroll attempt {attempts}: collected items from this window")
            except Exception as e:
                self.logger.warning(f"Playwright error during scroll (attempt {attempts}): {e}")
                break

        try:
            await page.close()
        except Exception:
            pass

    def parse_detail(self, response):
        item = self.auto_parse_item(
            response,
            title_xpath="//h1/text()",
        )

        item['author'] = "Zakon.kz"
        item['section'] = "Finansy"

        yield item
