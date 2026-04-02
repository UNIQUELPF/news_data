import scrapy
from bs4 import BeautifulSoup
from datetime import datetime
import json
import re
from news_scraper.spiders.base_spider import BaseNewsSpider

class MetiSpider(BaseNewsSpider):
    name = 'jp_meti'
    allowed_domains = ['meti.go.jp']
    start_urls = ['https://www.meti.go.jp/press/index.html']
    
    # 目标表名：jp_meti_news
    target_table = 'jp_meti_news'
    use_curl_cffi = True # 增加 curl_cffi 支持，应对可能的访问限制
    
    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.0,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 2,
    }


    def start_requests(self):
        # 1. 抓取当前主页
        yield scrapy.Request('https://www.meti.go.jp/press/index.html', callback=self.parse_list_ul)
        
        # 2. 抓取 2026 年各月存档 (回溯至 2026-01-01)
        # 格式: archive_202601.html, archive_202602.html, archive_202603.html
        for month in ['01', '02', '03']:
            archive_url = f'https://www.meti.go.jp/press/archive_2026{month}.html'
            yield scrapy.Request(archive_url, callback=self.parse_list_ul)

    def parse_list_ul(self, response):
        # 针对 archive 页面的 ul.clearfix.float_li 结构
        items = response.css('ul.clearfix.float_li li')
        for li in items:
            date_str = li.css('div.txt_box p::text').get()
            link = li.css('div.txt_box a.cut_txt::attr(href)').get()
            
            if link:
                url = response.urljoin(link)
                if url not in self.scraped_urls:
                    self.scraped_urls.add(url)
                    # 传递日期以便后续过滤
                    yield scrapy.Request(url, callback=self.parse_article, meta={'pub_date': date_str})

        # 同时也支持一下 dt/dd 结构 (如果主页是用这个的)
        dls = response.css('dl#release_menulist')
        if dls:
            dts = dls.css('dt')
            dds = dls.css('dd')
            for dt, dd in zip(dts, dds):
                date_str = dt.css('::text').get()
                link = dd.css('a::attr(href)').get()
                if link:
                    url = response.urljoin(link)
                    if url not in self.scraped_urls:
                        self.scraped_urls.add(url)
                        yield scrapy.Request(url, callback=self.parse_article, meta={'pub_date': date_str})

    def parse_article(self, response):
        item = {}
        item['url'] = response.url
        
        # 1. 标题提取 (h1 或 meta)
        title = response.css('h1::text').get() or response.xpath('//meta[@property="og:title"]/@content').get()
        item['title'] = title.strip() if title else ''

        # 2. 正文提取 (针对 METI 的特殊结构: h1 ID 为 MainContentsArea)
        # 尝试几种可能的容器
        content_area = response.css('div.main.w1000') or response.css('div#main')
        
        if content_area:
            # 提取 p, li (排除面包屑), h2, h3
            paragraphs = content_area.css('p::text, li::text, h2::text, h3::text').getall()
            # 过滤掉较短的噪音 (如面包屑导航)
            item['content'] = "\n\n".join([p.strip() for p in paragraphs if len(p.strip()) > 10])
        else:
            # 兜底：抓取所有文本
            texts = response.css('body ::text').getall()
            item['content'] = "\n\n".join([t.strip() for t in texts if len(t.strip()) > 30])

        # 3. 发布时间提取
        # 优先使用 meta 数据传递的日期，其次从页面抓取
        pub_time_str = response.meta.get('pub_date')
        if not pub_time_str:
            # 尝试从正文寻找日期 pattern (如 2026年3月23日)
            date_match = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日', response.text)
            if date_match:
                pub_time_str = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"

        pub_time = datetime.now()
        if pub_time_str:
            try:
                # 转换日本日期 2026年3月23日 -> 2026-03-23
                if '年' in pub_time_str:
                    pub_time_str = pub_time_str.replace('年', '-').replace('月', '-').replace('日', '')
                from dateutil import parser
                pub_time = parser.parse(pub_time_str).replace(tzinfo=None)
            except:
                pass

        # 4. 日期过滤 (2026-01-01)
        if not self.filter_date(pub_time):
            return

        item['publish_time'] = pub_time
        item['author'] = 'METI Japan'
        item['language'] = 'ja'
        item['section'] = 'Press Release'

        if item.get('content') and len(item['content']) > 100:
            yield item
