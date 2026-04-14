# 中国caixin spider爬虫，负责抓取对应站点、机构或栏目内容。

import scrapy
from scrapy_playwright.page import PageMethod
from news_scraper.items import CaixinHeadlineItem, CaixinMarketIndexItem
from datetime import datetime
from bs4 import BeautifulSoup
import psycopg2
import re

class CaixinSpider(scrapy.Spider):
    name = 'caixin'

    country_code = 'CHN'

    country = '中国'
    allowed_domains = ['finance.caixin.com']
    start_urls = ['https://finance.caixin.com/']

    def __init__(self, *args, **kwargs):
        super(CaixinSpider, self).__init__(*args, **kwargs)
        self.is_first_run = True

    def check_if_first_run(self):
        db_settings = self.settings.get('POSTGRES_SETTINGS')
        try:
            conn = psycopg2.connect(**db_settings)
            cur = conn.cursor()
            # 检查统一的 articles 表中是否已经有来自财新的数据
            cur.execute("SELECT count(*) FROM articles WHERE legacy_table = 'caixin'")
            count = cur.fetchone()[0]
            cur.close()
            conn.close()
            return count == 0
        except Exception as e:
            self.logger.error(f"Failed to check DB status for Caixin: {e}")
            return True

    def check_url_exists(self, url):
        db_settings = self.settings.get('POSTGRES_SETTINGS')
        try:
            conn = psycopg2.connect(**db_settings)
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM news_articles WHERE url = %s", (url,))
            exists = cur.fetchone() is not None
            cur.close()
            conn.close()
            return exists
        except Exception as e:
            self.logger.error(f"Failed to check URL existence: {e}")
            return False

    def start_requests(self):
        self.is_first_run = self.check_if_first_run()
        
        # JS 脚本：点击“加载更多”直到结束（仅限首次运行）
        # 翻页 30 次约可覆盖几周数据
        # 改进：即使不是首次运行，也至少滚动 5 次以确保抓取到最新的动态内容
        scroll_count = 30 if self.is_first_run else 5
        js_script = f"""
        async () => {{
            let attempts = 0;
            while (attempts < {scroll_count}) {{
                window.scrollTo(0, document.body.scrollHeight);
                await new Promise(r => setTimeout(r, 1000));
                const buttons = Array.from(document.querySelectorAll('a, div, span'));
                const loadMore = buttons.find(b => b.innerText && b.innerText.includes('加载更多文章'));
                if (loadMore) {{
                    loadMore.click();
                    await new Promise(r => setTimeout(r, 2000));
                }} else {{
                    break;
                }}
                attempts++;
            }}
        }}
        """

        for url in self.start_urls:
            yield scrapy.Request(
                url,
                meta={
                    "playwright": True,
                    "playwright_page_methods": [
                        PageMethod("wait_for_selector", ".ywListCon"),
                        PageMethod("evaluate", js_script) if js_script else PageMethod("wait_for_timeout", 1000),
                    ],
                },
                callback=self.parse
            )

    def parse(self, response):
        soup = BeautifulSoup(response.text, 'html.parser')
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        self.logger.info(f"Caixin Filtering headlines. First run: {self.is_first_run}, Today: {today_str}")

        # 1. 提取要闻
        headlines = soup.select('.ywListCon .boxa')
        for box in headlines:
            link_tag = box.select_one('h4 a')
            span_tag = box.select_one('span')
            
            if link_tag:
                url = response.urljoin(link_tag.get('href'))
                title = link_tag.get_text(strip=True)
                
                # 提取日期 (格式: /2026-01-25/)
                item_date_str = None
                m = re.search(r'(\d{4}-\d{2}-\d{2})', url)
                if m:
                    item_date_str = m.group(1)
                
                # 如果 URL 里没找到，尝试从 span 里提取
                if not item_date_str and span_tag:
                    m = re.search(r'(\d{4})年(\d{2})月(\d{2})日', span_tag.get_text())
                    if m:
                        item_date_str = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"

                # 改进逻辑：检查数据库中是否已存在该 URL
                should_yield = not self.check_url_exists(url)
                
                if should_yield:
                    headline_item = CaixinHeadlineItem()
                    headline_item['type'] = 'headline'
                    headline_item['title'] = title
                    headline_item['url'] = url
                    headline_item['crawl_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    yield headline_item

        # 2. 提取今日开盘
        for dl in soup.find_all('dl'):
            if "今日开盘" in dl.get_text():
                dt = dl.find('dt')
                span = dl.find('span')
                p_tag = dl.find('p')
                
                if dt and span and p_tag:
                    index_item = CaixinMarketIndexItem()
                    index_item['type'] = 'market_index'
                    index_item['title'] = dt.get_text(strip=True)
                    index_item['time'] = span.get_text(strip=True)
                    index_item['detail'] = p_tag.get_text(strip=True)
                    index_item['crawl_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    yield index_item
