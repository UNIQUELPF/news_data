import scrapy
import re
from datetime import datetime
import dateparser
from scrapy_playwright.page import PageMethod
from news_scraper.spiders.smart_spider import SmartSpider
from pipeline.content_engine import ContentEngine


class NewsCNSpider(SmartSpider):
    """
    Modernized China News Spider (V2 Architecture - Refined).
    Follows all guidelines in modernize_spider skill.
    """
    name = 'news_cn'
    source_timezone = 'Asia/Shanghai'
    country_code = 'CHN'
    country = '中国'
    language = 'zh'
    
    # Chinese sites always use Year-Month-Day order
    dateparser_settings = {"DATE_ORDER": "YMD"}
    
    use_curl_cffi = True
    allowed_domains = ['news.cn']
    
    # Tight selector for Xinhuanet article body (includes unconventional span#detailContent)
    fallback_content_selector = "#detailContent, #detail .main-content, #content, .content, .article"
    
    CHANNELS = {
        'finance': {
            'url': 'https://www.news.cn/fortune/index.htm',
            'list_selector': '#recommendDepth .xpage-content-list',
            'item_selector': '.column-center-item',
            'wait_selector': '#recommendDepth',
            'name': '财经'
        },
        'money': {
            'url': 'https://www.news.cn/money/index.html',
            'list_selector': 'ul.infoList',
            'item_selector': 'li',
            'wait_selector': 'ul.infoList',
            'name': '金融'
        },
        'silkroad': {
            'urls': {
                '丝路聚焦': 'https://www.news.cn/silkroad/jj/index.html',
                '丝路议程': 'https://www.news.cn/silkroad/slyc/index.html',
                '丝路商商机': 'https://www.news.cn/silkroad/slsj/index.html',
            },
            'list_selector': 'ul#autoData',
            'item_selector': 'li',
            'wait_selector': 'ul#autoData',
            'name': '一带一路'
        }
    }

    custom_settings = {
        'CONCURRENT_REQUESTS': 2,
        'DOWNLOAD_DELAY': 1.5,
        'AUTOTHROTTLE_ENABLED': True,
        'PLAYWRIGHT_LAUNCH_OPTIONS': {"headless": True, "timeout": 60000},
    }

    async def start(self):
        """Unified start logic with smart scrolling and date-based termination."""
        target_date_str = self.cutoff_date.strftime('%Y%m%d') if self.cutoff_date else '20260101'
        
        js_scroll = f"""
        async () => {{
            let stopCount = 0;
            for (let i = 0; i < 30; i++) {{
                window.scrollTo(0, document.body.scrollHeight);
                await new Promise(r => setTimeout(r, 1500));
                
                const links = Array.from(document.querySelectorAll('a[href*="/202"]'));
                const earlyLinks = links.filter(l => {{
                    const m = l.href.match(/\\/(\\d{{8}})\\//);
                    return m && m[1] < "{target_date_str}";
                }});
                
                if (earlyLinks.length > 5) stopCount++;
                if (stopCount >= 2) break;

                const loadMore = document.querySelector('.xpage-more-btn.look, .xpage-more-btn, #loadMore, .more');
                if (loadMore && loadMore.offsetParent !== null) {{
                    loadMore.click();
                    await new Promise(r => setTimeout(r, 1500));
                }}
            }}
        }}
        """

        for _, config in self.CHANNELS.items():
            urls = []
            if 'url' in config:
                urls.append((config['url'], config['name']))
            if 'urls' in config:
                for sub_name, url in config['urls'].items():
                    urls.append((url, f"{config['name']}-{sub_name}"))

            for url, section_name in urls:
                yield scrapy.Request(
                    url,
                    meta={
                        "playwright": True,
                        "playwright_page_methods": [
                            PageMethod("wait_for_selector", config['wait_selector'], timeout=10000),
                            PageMethod("evaluate", js_scroll),
                        ],
                        "channel_config": config,
                        "section_hint": section_name
                    },
                    callback=self.parse_list,
                    dont_filter=True
                )

    def parse_list(self, response):
        """Standard V2 list parsing with date-based circuit breaker."""
        config = response.meta['channel_config']
        section_hint = response.meta['section_hint']
        
        articles = response.css(f"{config['list_selector']} {config['item_selector']}")
        self.logger.info(f"Processing list {response.url}: found {len(articles)} items.")

        has_valid_item_in_window = False

        for art in articles:
            url = art.css('a::attr(href)').get()
            if not url: continue
            
            abs_url = response.urljoin(url)
            if not (abs_url.endswith('.html') or abs_url.endswith('.htm')):
                continue

            date_str = art.css('.time::text, .date::text, span:contains("202")::text').get()
            publish_time = None
            if date_str:
                dt_local = dateparser.parse(date_str.strip())
                publish_time = self.parse_to_utc(dt_local) if dt_local else None
            
            if not publish_time:
                m = re.search(r'/(\d{8})/', abs_url)
                if m:
                    dt_url = datetime.strptime(m.group(1), '%Y%m%d')
                    publish_time = self.parse_to_utc(dt_url)

            if not self.should_process(abs_url, publish_time):
                continue

            has_valid_item_in_window = True
            yield scrapy.Request(
                abs_url,
                callback=self.parse_detail,
                dont_filter=self.full_scan,
                meta={
                    "section_hint": section_hint,
                    "publish_time_hint": publish_time,
                }
            )

    def extract_content(self, response):
        """
        Xinhuanet uses span#detailContent which often flattens paragraphs in parsers.
        We convert it to a div and aggressively inject newlines.
        """
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.text, 'lxml')
        
        # 1. Normalize the problematic span#detailContent to a div
        main_content = soup.select_one("#detailContent")
        if main_content and main_content.name == 'span':
            main_content.name = 'div'
            self.logger.info(f"Converted span#detailContent to div for {response.url}")

        raw_html = str(soup)
        
        # 2. Aggressive Injection: Add double newlines around block-level tags
        block_tags = ['p', 'div', 'section', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'br']
        for tag in block_tags:
            raw_html = re.sub(f'<{tag}([^>]*)>', f'\n\n<{tag}\\1>', raw_html, flags=re.IGNORECASE)
            raw_html = re.sub(f'</{tag}>', f'</{tag}>\n\n', raw_html, flags=re.IGNORECASE)
        
        raw_html = re.sub(r'<br\s*/?>', '\n\n<br/>\n\n', raw_html, flags=re.IGNORECASE)
        
        return ContentEngine.process(
            raw_html=raw_html,
            base_url=response.url,
            fallback_selector=self.fallback_content_selector
        )

    def parse_detail(self, response):
        """Refined detail parsing with explicit XPaths."""
        item = self.auto_parse_item(
            response,
            title_xpath="//h1[contains(@class,'atitle')]/text() | //div[contains(@class,'header-content')]/h1/text() | //h1[@id='title']/text()",
        )

        # 1. Custom precise publish time extraction (with time components)
        publish_time = None
        
        # Try joining header-time text nodes (desktop view)
        header_time_nodes = response.xpath("//div[contains(@class,'header-time')]//text() | //span[contains(@class,'header-time')]//text()").getall()
        if header_time_nodes:
            raw_time = "".join(header_time_nodes).strip()
            raw_time = re.sub(r'\s+', ' ', raw_time)
            if raw_time:
                publish_time = self.parse_date(raw_time)

        # Try mobile header info if still no precise time
        if not publish_time:
            raw_time = response.xpath("//div[contains(@class, 'mheader')]//div[@class='info']/text()").get()
            if raw_time:
                publish_time = self.parse_date(raw_time.strip())

        # If custom extraction succeeded, override item['publish_time']
        if publish_time:
            item['publish_time'] = publish_time

        item['author'] = item.get('author') or "新华网"
        item['section'] = response.meta.get('section_hint', '综合')
        
        # Skill optimization: manually exclude common noise icons
        if item.get('images'):
            item['images'] = [img for img in item['images'] if not any(x in img.lower() for x in ['icon', 'logo', 'share', 'qrcode'])]

        yield item
