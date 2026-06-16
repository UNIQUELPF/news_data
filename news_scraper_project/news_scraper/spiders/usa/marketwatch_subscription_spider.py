from news_scraper.spiders.usa.rss_feed_base import USARssFeedSpider


class USAMarketWatchSpider(USARssFeedSpider):
    name = "usa_marketwatch_subscription"
    subscription_required = True
    access_note = "订阅/付费墙网站；仅采集可访问的公开正文，正文不全时需标记"
    source_name = "MarketWatch Latest News"
    organization = "MarketWatch"
    allowed_domains = ["marketwatch.com"]
    section_name = "Markets and Economy"
    feed_urls = ["https://feeds.marketwatch.com/marketwatch/topstories/"]
