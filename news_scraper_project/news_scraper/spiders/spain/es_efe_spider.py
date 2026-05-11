import scrapy
from datetime import datetime
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from news_scraper.spiders.smart_spider import SmartSpider

class EsEfeSpider(SmartSpider):
    name = 'es_efe'
    source_timezone = 'Europe/Madrid'

    country_code = 'ESP'

    country = '西班牙'
    language = 'es'
    allowed_domains = ['efe.com']

    strict_date_required = True
    use_curl_cffi = True
    fallback_content_selector = "div.entry-content, .inside-article, article, .elementor-widget-theme-post-content"

    # 埃菲社板块
    base_url = 'https://efe.com/portada-espana/page/{}/'

    custom_settings = {
        'DOWNLOAD_DELAY': 3.0,
        'CONCURRENT_REQUESTS': 2,
        'DOWNLOADER_MIDDLEWARES': {
            'news_scraper.middlewares.CurlCffiMiddleware': 101,
            'news_scraper.middlewares.BatchDelayMiddleware': 600,
        },
    }

    async def start(self):
        yield scrapy.Request(
            self.base_url.format(1),
            callback=self.parse,
            dont_filter=True,
            meta={'page_idx': 1}
        )

    def parse(self, response):
        self.logger.info(f"PARSE_TRIGGERED: {response.url}, Title: {response.css('title::text').get()}")

        # 1. 提取新闻链接 (支持 Elementor 和传统 WP 结构)
        articles = response.css('h2.elementor-heading-title a, h2.entry-title a')

        current_page = response.meta.get('page_idx', 1)
        has_valid_item_in_window = False

        for art in articles:
            link = art.css('::attr(data-mrf-link)').get() or art.css('::attr(href)').get()
            if not link: continue

            absolute_link = response.urljoin(link)

            # 日期正则检测
            date_match = re.search(r'/(\d{4})-(\d{2})-(\d{2})/', absolute_link)
            if date_match:
                y, m, d = date_match.groups()
                try:
                    pub_time = datetime(year=int(y), month=int(m), day=int(d))
                except: continue

                if not self.should_process(absolute_link, pub_time):
                    continue

                has_valid_item_in_window = True
                yield response.follow(
                    absolute_link,
                    self.parse_detail,
                    meta={'publish_time_hint': pub_time}
                )

        # 翻页
        if has_valid_item_in_window:
            next_page = current_page + 1
            yield scrapy.Request(
                self.base_url.format(next_page),
                callback=self.parse,
                dont_filter=True,
                meta={'page_idx': next_page}
            )

    def _extract_content(self, response):
        """Custom content extraction for EFE's Elementor-based article pages.
        EFE uses Elementor with no standard article/article-entry classes,
        so ContentEngine/trafilatura fails. This method extracts directly
        from the Elementor post-content widget area using bs4.
        """
        soup = BeautifulSoup(response.text, 'lxml')

        # --- Title ---
        title = None
        og_title = soup.select_one('meta[property="og:title"]')
        if og_title:
            title = og_title.get('content', '').strip()
            if title.endswith(' - EFE'):
                title = title[:-5]

        if not title:
            h1 = soup.select_one('h1.elementor-heading-title')
            if h1:
                title = h1.get_text(strip=True)

        # --- Publish time from URL ---
        pub_time = None
        date_match = re.search(r'/(\d{4})-(\d{2})-(\d{2})/', response.url)
        if date_match:
            y, m, d = date_match.groups()
            pub_time = datetime(int(y), int(m), int(d))

        # --- Content ---
        content_area = soup.select_one(
            'div.elementor-widget-theme-post-content div.elementor-widget-container'
        )
        if not content_area:
            content_area = soup.select_one('div.elementor-widget-theme-post-content')

        if not content_area:
            return None

        # Remove noise
        for tag in content_area.find_all(
            ['script', 'style', 'nav', 'footer', 'header', 'aside', 'form',
             'button', 'iframe']
        ):
            tag.decompose()
        for share in content_area.select('.addtoany_share_save_container'):
            share.decompose()
        for banner in content_area.select('.auto-banner'):
            banner.decompose()
        for div in content_area.find_all('div', class_=lambda c: c and 'banner' in c.lower()):
            div.decompose()

        # Extract paragraphs
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
                "publish_time": pub_time,
            }

        return None

    def parse_detail(self, response):
        # Try custom content extraction first (targets EFE's Elementor structure)
        content_data = self._extract_content(response)
        if content_data and content_data.get('content_plain') and len(content_data['content_plain']) > 50:
            item = {
                **content_data,
                "url": response.url,
                "raw_html": response.text,
                "language": self.language,
                "section": 'España',
                "country_code": self.country_code,
                "country": self.country,
                "author": 'EFE News',
            }
            yield item
        else:
            item = self.auto_parse_item(response)
            item['author'] = 'EFE News'
            item['section'] = 'España'
            yield item
