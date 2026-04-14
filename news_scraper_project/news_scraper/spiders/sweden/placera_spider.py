import scrapy
from datetime import datetime
import re
from news_scraper.spiders.base_spider import BaseNewsSpider


class PlaceraSESpider(BaseNewsSpider):
    """
    瑞典 Placera.se 新闻爬虫
    策略：通过 sitemap.xml 获取文章 URL 列表，再逐个抓详情页
    """
    name = 'se_placera'

    country_code = 'SWE'

    country = '瑞典'
    allowed_domains = ['placera.se']
    target_table = 'se_placera_news'
    use_curl_cffi = True

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.0,
        'CONCURRENT_REQUESTS': 8,
    }



    def start_requests(self):
        """先请求主 sitemap，找到 2026 年的月度子 sitemap"""
        yield scrapy.Request(
            'https://www.placera.se/sitemap.xml',
            callback=self.parse_sitemap_index,
            meta={'use_curl_cffi': True},
        )

    def parse_sitemap_index(self, response):
        """解析 sitemap 索引，提取 2026 年的月度 sitemap"""
        sel = scrapy.Selector(response, type='xml')
        sel.remove_namespaces()
        urls = sel.css('loc::text').getall()

        for url in urls:
            if '2026-' in url:
                self.logger.info(f"Found 2026 sitemap: {url}")
                yield scrapy.Request(
                    url,
                    callback=self.parse_monthly_sitemap,
                    meta={'use_curl_cffi': True},
                )

    def parse_monthly_sitemap(self, response):
        """解析月度 sitemap，提取所有文章 URL"""
        sel = scrapy.Selector(response, type='xml')
        sel.remove_namespaces()
        urls = sel.css('loc::text').getall()

        self.logger.info(f"Monthly sitemap: {len(urls)} article URLs found")

        for url in urls:
            if '/nyheter/' in url and url not in self.scraped_urls:
                self.scraped_urls.add(url)
                yield scrapy.Request(
                    url,
                    callback=self.parse_article,
                    meta={'use_curl_cffi': True},
                )

    def parse_article(self, response):
        """解析文章详情页"""


        item = {}
        item['url'] = response.url

        # 标题：og:title（去掉 " | Placera.se" 后缀）
        title = response.xpath('//meta[@property="og:title"]/@content').get()
        if not title:
            h1_texts = response.css('h1 *::text').getall()
            title = ' '.join([t.strip() for t in h1_texts if t.strip()])
        if title:
            title = re.sub(r'\s*\|\s*Placera\.se$', '', title).strip()
        item['title'] = title or ''

        # 日期：从 URL 提取 YYYY-MM-DD
        date_match = re.search(r'(\d{4}-\d{2}-\d{2})', response.url)
        if date_match:
            try:
                pub_time = datetime.strptime(date_match.group(1), '%Y-%m-%d')
            except ValueError:
                pub_time = datetime.now()
        else:
            pub_time = datetime.now()

        if not self.filter_date(pub_time):
            return

        # 正文：article 标签中的 p 文本，过滤短文本
        paragraphs = response.css('article p::text').getall()
        filtered = [p.strip() for p in paragraphs if len(p.strip()) > 40]
        content = '\n\n'.join(filtered)
        item['content'] = content

        if not content or len(content) < 50:
            self.logger.debug(f"Skipping (short content): {response.url}")
            return

        item['publish_time'] = pub_time
        item['author'] = 'Placera'
        item['language'] = 'sv'
        item['section'] = 'Nyheter'

        self.logger.info(f"Saved: {item['title']}")
        yield item
