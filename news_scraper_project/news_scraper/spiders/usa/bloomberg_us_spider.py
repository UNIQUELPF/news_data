from news_scraper.spiders.usa.rss_feed_base import USARssFeedSpider


class USABloombergSpider(USARssFeedSpider):
    name = "usa_bloomberg"
    source_name = "Bloomberg Economics"
    organization = "Bloomberg"
    allowed_domains = ["bloomberg.com"]
    section_name = "Economics"
    feed_urls = ["https://feeds.bloomberg.com/economics/news.rss"]
