import scrapy
from datetime import datetime
from news_scraper.spiders.base_spider import BaseNewsSpider

class FinewsCHSpider(BaseNewsSpider):
    name = 'ch_finews'
    allowed_domains = ['finews.com']
    start_urls = ['https://www.finews.com/news/english-news']
    target_table = 'ch_finews_news'
    use_curl_cffi = True

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.5,
        'CONCURRENT_REQUESTS': 2,
    }



    def parse(self, response):
        # 提取文章链接
        articles = response.css('div.teaser-element')
        for article in articles:
            link = article.css('a::attr(href)').get()
            if link:
                yield response.follow(link, self.parse_article)

        # 翻页逻辑 (?start=19, 38...)
        if current_start.isdigit():
            next_start = int(current_start) + 19
            # 持续翻页，BaseNewsSpider 的 filter_date 会自动停止
            next_url = f"https://www.finews.com/news/english-news?start={next_start}"
            yield response.follow(next_url, self.parse)

    def parse_article(self, response):
        item = {}
        item['url'] = response.url
        item['title'] = response.css('h2.item-title::text, h1::text').get('').strip()
        
        # 正文
        paragraphs = response.css('div.item-fulltext p::text, div.article-body p::text').getall()
        item['content'] = '\n\n'.join([p.strip() for p in paragraphs if p.strip()])

        # 时间 (通常在 meta 或 特定 span 中)
        pub_time_str = response.css('span.article-date::attr(content), meta[property="article:published_time"]::attr(content)').get()
        try:
            pub_time = datetime.fromisoformat(pub_time_str.replace('Z', '+00:00')) if pub_time_str else datetime.now()
        except:
            pub_time = datetime.now()

        if not self.filter_date(pub_time):
            return

        item['publish_time'] = pub_time
        item['author'] = response.css('span.author-name::text').get('finews.com').strip()
        item['language'] = 'en'
        item['section'] = 'Financial News'

        yield item
