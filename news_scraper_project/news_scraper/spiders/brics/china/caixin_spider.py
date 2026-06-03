# 中国caixin spider爬虫，负责抓取对应站点、机构或栏目内容。

import scrapy
import re
from news_scraper.spiders.smart_spider import SmartSpider

class CaixinSpider(SmartSpider):
    name = 'caixin'
    source_timezone = 'Asia/Shanghai'
    country_code = 'CHN'
    country = '中国'
    language = 'zh'
    dateparser_settings = {"DATE_ORDER": "YMD"}

    allowed_domains = ['finance.caixin.com']
    start_urls = ['https://finance.caixin.com/']

    use_curl_cffi = True
    fallback_content_selector = "div#the_content, div.content, div.article"

    custom_settings = {
        'CONCURRENT_REQUESTS': 2,
        'DOWNLOAD_DELAY': 1.5,
        'AUTOTHROTTLE_ENABLED': True,
    }

    async def start(self):
        for url in self.start_urls:
            yield scrapy.Request(
                url,
                callback=self.parse_list,
                dont_filter=True,
            )

    def parse_list(self, response):
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 提取要闻列表
        headlines = soup.select('.ywListCon .boxa')
        self.logger.info(f"Found {len(headlines)} articles in listing.")
        
        for box in headlines:
            link_tag = box.select_one('h4 a')
            span_tag = box.select_one('span')
            
            if link_tag:
                url = response.urljoin(link_tag.get('href'))
                title = link_tag.get_text(strip=True)
                
                # 尝试从 URL 中匹配日期 (例如: /2026-05-19/)
                item_date_str = None
                m = re.search(r'(\d{4}-\d{2}-\d{2})', url)
                if m:
                    item_date_str = m.group(1)
                
                # 若 URL 未匹配到日期，从 span 的文本中匹配
                if not item_date_str and span_tag:
                    m = re.search(r'(\d{4})年(\d{2})月(\d{2})日', span_tag.get_text())
                    if m:
                        item_date_str = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
                
                publish_time = self.parse_date(item_date_str) if item_date_str else None
                
                if not self.should_process(url, publish_time):
                    continue
                
                yield scrapy.Request(
                    url,
                    callback=self.parse_detail,
                    dont_filter=True,
                    meta={
                        "title_hint": title,
                        "publish_time_hint": publish_time,
                        "section_hint": "金融" if "finance.caixin.com" in url else "综合"
                    }
                )

    def parse_detail(self, response):
        # 自动提取文章标题、正文、发布时间等字段
        item = self.auto_parse_item(
            response,
            title_xpath='//div[@id="conTit"]/h1/text()',
            publish_time_xpath='//span[@id="pubtime_baidu"]/text()'
        )
        
        # 覆盖并填充其他信息
        item['author'] = item.get('author') or "财新网"
        item['section'] = response.meta.get('section_hint', '综合')
        
        # 清理常见的冗余图标/分享图
        if item.get('images'):
            item['images'] = [img for img in item['images'] if not any(x in img.lower() for x in ['icon', 'logo', 'share', 'qrcode'])]
            
        yield item
