# 哈萨克斯坦informburo spider爬虫，负责抓取对应站点、机构或栏目内容。

import scrapy
from datetime import datetime
import re
import asyncio
from bs4 import BeautifulSoup
from news_scraper.spiders.smart_spider import SmartSpider


class InformburoSpider(SmartSpider):
    name = 'informburo'

    country_code = 'KAZ'
    country = '哈萨克斯坦'
    language = 'ru'
    source_timezone = 'Asia/Almaty'

    start_date = '2024-01-01'
    fallback_content_selector = 'article.article-content'
    # URLs no longer contain dates; we rely on detail pages for date extraction
    strict_date_required = False

    allowed_domains = ['informburo.kz']
    start_urls = ['https://informburo.kz/']

    @staticmethod
    def extract_date_from_url(url):
        """Extracts YYYYMMDD from URL using regex r'/(\d{8})/'."""
        match = re.search(r'/(\d{8})/', url)
        if match:
            try:
                return datetime.strptime(match.group(1), "%Y%m%d")
            except ValueError:
                return None
        return None

    def start_requests(self):
        url = "https://informburo.kz/"
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
            dont_filter=True,
        )

    async def parse_list(self, response):
        page = response.meta['playwright_page']

        target_header = "ГЛАВНЫЕ НОВОСТИ"
        news_list = []
        has_valid_item_in_window = False

        section_locator = page.locator(f".uk-container:has-text('{target_header}')")
        load_more_btn = section_locator.locator("text='Показать больше'")

        attempts = 0
        while attempts < 100:
            html = await page.content()
            soup = BeautifulSoup(html, 'html.parser')

            # Debug: Log all containers
            for idx, c in enumerate(soup.select('.uk-container')):
                self.logger.info(f"Container {idx} text summary: {c.get_text()[:100]}...")

            target_container = None
            for c in soup.select('.uk-container'):
                h_tags = c.select('h1, h2, h3')
                for h in h_tags:
                    if target_header in h.get_text():
                        self.logger.info(f"Found target header in container: {h.get_text()}")
                        target_container = c
                        break
                if target_container:
                    break

            if not target_container:
                # Fallback: check all headers directly
                self.logger.info("Retrying container lookup by header...")
                all_h = soup.find_all(['h1', 'h2', 'h3'])
                for h in all_h:
                    if target_header in h.get_text():
                        self.logger.info(f"Found free-standing header: {h.get_text()}")
                        target_container = h.find_parent('div', class_='uk-container') or h.find_parent('section')
                        break

            if not target_container:
                self.logger.error("Target section container not found. Check if page loaded correctly.")
                break

            # Articles are typically div.uk-width-1-2@m or similar inside the container
            articles = target_container.select('article, .article-card, .uk-width-1-2')
            for art in articles:
                link_el = art.select_one('a[href*="/novosti/"]')
                if not link_el:
                    continue

                href = link_el.get('href')
                full_url = response.urljoin(href)

                img_el = art.select_one('img.article-card-thumb')
                title = img_el.get('alt', '').strip() if img_el else ""
                if not title:
                    title = art.get_text(strip=True)

                # Date extraction is deferred to the detail page (URLs no longer contain dates)
                self.logger.info(f"Checking article: {title}")

                if not self.should_process(full_url, None):
                    continue

                if not any(a['url'] == full_url for a in news_list):
                    has_valid_item_in_window = True
                    news_list.append({
                        "title": title,
                        "url": full_url,
                    })

            if await load_more_btn.count() > 0:
                self.logger.info(f"Clicking 'Показать больше'... ({len(news_list)} items)")
                try:
                    await load_more_btn.click()
                    await asyncio.sleep(2)
                except Exception as e:
                    self.logger.warning(f"Click failed: {e}")
                    break
            else:
                self.logger.info("No more 'Показать больше' button found.")
                break

            attempts += 1

        await page.close()

        for item_data in news_list:
            yield scrapy.Request(
                item_data['url'],
                callback=self.parse_detail,
                dont_filter=self.full_scan,
            )

    def parse_detail(self, response):
        item = self.auto_parse_item(
            response,
            title_xpath="//h1//text()",
        )

        if not self.should_process(response.url, item.get('publish_time')):
            return

        yield item
