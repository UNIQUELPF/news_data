import scrapy
from datetime import datetime
import re
from news_scraper.spiders.base_spider import BaseNewsSpider

class GovernmentSESpider(BaseNewsSpider):
    name = 'se_government'
    allowed_domains = ['government.se']
    start_urls = ['https://www.government.se/government-policy/economic-policy/']
    target_table = 'se_government_news'
    use_curl_cffi = True

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.0,
        'CONCURRENT_REQUESTS': 2,
    }



    def parse(self, response):
        # 提取文章链接
        links = response.css('div.sortcompact.sortextended a::attr(href)').getall()
        for link in links:
            yield response.follow(link, self.parse_article)

        # 翻页
        next_page = response.css('li.nav--pagination__next a::attr(href)').get()
        if next_page:
            yield response.follow(next_page, self.parse)

    def parse_article(self, response):
        item = {}
        item['url'] = response.url
        item['title'] = response.css('h1::text').get('').strip() or response.xpath('//meta[@property="og:title"]/@content').get('').strip()
        
        # 正文
        paragraphs = response.css('div.article__body p::text, div.article__body p *::text').getall()
        item['content'] = '\n\n'.join([p.strip() for p in paragraphs if p.strip()])

        # 时间
        pub_time_str = response.xpath('//meta[@property="article:published_time"]/@content').get()
        if not pub_time_str:
            # 尝试从 URL 提取
            date_match = re.search(r'/articles/(\d{4}/\d{2})/', response.url)
            pub_time_str = date_match.group(1).replace('/', '-') + '-01' if date_match else None
        
        try:
            pub_time = datetime.fromisoformat(pub_time_str.replace('Z', '+00:00')) if pub_time_str else datetime.now()
        except:
            pub_time = datetime.now()

        if not self.filter_date(pub_time):
            return

        item['publish_time'] = pub_time
        item['author'] = 'Government of Sweden'
        item['language'] = 'en'
        item['section'] = 'Economic Policy'

        yield item
