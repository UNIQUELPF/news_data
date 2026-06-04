from news_scraper.spiders.usa.rss_feed_base import USARssFeedSpider


class USAMarketWatchSpider(USARssFeedSpider):
    name = "usa_marketwatch"
    source_name = "MarketWatch Latest News"
    organization = "MarketWatch"
    allowed_domains = ["marketwatch.com"]
    section_name = "Markets and Economy"
    feed_urls = ["https://feeds.marketwatch.com/marketwatch/topstories/"]
