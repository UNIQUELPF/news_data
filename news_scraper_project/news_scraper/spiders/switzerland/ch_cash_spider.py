import scrapy
from datetime import datetime
from news_scraper.spiders.base_spider import BaseNewsSpider

class CashCHSpider(BaseNewsSpider):
    name = 'ch_cash'
    allowed_domains = ['cash.ch']
    start_urls = ['https://www.cash.ch/news/top-news']
    target_table = 'ch_cash_news'
    use_curl_cffi = True

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 2.0,
        'CONCURRENT_REQUESTS': 1,
    }



    def parse(self, response):
        # 提取文章链接
        links = response.css('a.teaser-image::attr(href), a.teaser-text-link::attr(href), div.c_jLL_d9 a::attr(href)').getall()
        for link in set(links):
            if '/news/' in link:
                yield response.follow(link, self.parse_article)

        # 翻页逻辑 ?page=2
        next_page = response.css('a.page-loader-next-btn::attr(href)').get()
        if next_page:
            yield response.follow(next_page, self.parse)

    def parse_article(self, response):
        item = {}
        item['url'] = response.url
        item['title'] = response.css('h1::text, span.article-title::text').get('').strip()
        
        # 正文
        paragraphs = response.css('div.article-body p::text, div.content-wrapper p::text').getall()
        item['content'] = '\n\n'.join([p.strip() for p in paragraphs if p.strip()])

        # 时间
        pub_time_str = response.css('meta[property="article:published_time"]::attr(content)').get()
        try:
            pub_time = datetime.fromisoformat(pub_time_str.replace('Z', '+00:00')) if pub_time_str else datetime.now()
        except:
            pub_time = datetime.now()

        if not self.filter_date(pub_time):
            return

        item['publish_time'] = pub_time
        item['author'] = response.css('span.author::text').get('cash.ch').strip()
        item['language'] = 'de'
        item['section'] = 'Top News'

        yield item
