# 哈萨克斯坦informburo spider爬虫，负责抓取对应站点、机构或栏目内容。

import scrapy
from news_scraper.items import InformburoItem
from datetime import datetime
import re
from bs4 import BeautifulSoup
import asyncio
from news_scraper.utils import get_dynamic_cutoff

class InformburoSpider(scrapy.Spider):
    name = 'informburo'
    allowed_domains = ['informburo.kz']
    start_urls = ['https://informburo.kz/']
    
    CUTOFF_DATE = None

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super(InformburoSpider, cls).from_crawler(crawler, *args, **kwargs)
        spider.CUTOFF_DATE = get_dynamic_cutoff(crawler.settings, 'news_informburo')
        return spider

    def extract_date_from_url(self, url):
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
            callback=self.parse_list
        )

    async def parse_list(self, response):
        page = response.meta['playwright_page']
        
        target_header = "ГЛАВНЫЕ НОВОСТИ"
        cutoff_date = self.CUTOFF_DATE
        news_list = []
        stop_crawling = False
        
        section_locator = page.locator(f".uk-container:has-text('{target_header}')")
        load_more_btn = section_locator.locator("text='Показать больше'")
        
        attempts = 0
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
                if target_container: break
            
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
                # Save page source for extreme debugging if needed
                # with open("debug_page.html", "w") as f: f.write(html)
                break
                
            # Articles are typically div.uk-width-1-2@m or similar inside the container
            articles = target_container.select('article, .article-card, .uk-width-1-2')
            for art in articles:
                link_el = art.select_one('a[href*="/novosti/"]')
                if not link_el: continue
                
                href = link_el.get('href')
                full_url = response.urljoin(href)
                
                img_el = art.select_one('img.article-card-thumb')
                title = img_el.get('alt', '').strip() if img_el else ""
                if not title:
                    title = art.get_text(strip=True)
                
                self.logger.info(f"Checking article: {title}")
                
                url_date = self.extract_date_from_url(full_url)
                if url_date and url_date < cutoff_date:
                    self.logger.info(f"Reached cutoff date {url_date.date()}. Stopping.")
                    stop_crawling = True
                    break
                
                if not any(a['url'] == full_url for a in news_list):
                    news_list.append({
                        "title": title,
                        "url": full_url,
                        "publish_time": url_date if url_date else None
                    })

            if stop_crawling:
                break
            
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

        for item in news_list:
            yield scrapy.Request(
                item['url'],
                callback=self.parse_detail,
                meta={'item_data': item}
            )

    def parse_detail(self, response):
        item_data = response.meta['item_data']
        soup = BeautifulSoup(response.text, 'html.parser')
        
        content_div = soup.select_one('article.article-content, section.article-body, #detailContent')
        full_text = ""
        publish_time = item_data['publish_time']
        
        if content_div:
            for s in content_div.select('script, style, .social-buttons, .uk-button-group, .related-news'):
                s.decompose()
            
            paragraphs = [p.get_text(strip=True) for p in content_div.find_all('p')]
            cleaned_paragraphs = []
            for p in paragraphs:
                if not p: continue
                if any(skip in p for skip in ["Ответственный редактор", "Фото:", "Фото с сайта", "Была ли эта статья"]):
                    continue
                cleaned_paragraphs.append(p)
            
            full_text = "\n\n".join(cleaned_paragraphs)
            
            if not publish_time:
                time_tag = soup.select_one('time')
                if time_tag and time_tag.get('datetime'):
                    publish_time = time_tag.get('datetime')

        item = InformburoItem()
        item['type'] = 'informburo'
        item['title'] = item_data['title']
        item['url'] = item_data['url']
        item['publish_time'] = publish_time
        item['content'] = full_text
        item['crawl_time'] = datetime.now()
        
        yield item
