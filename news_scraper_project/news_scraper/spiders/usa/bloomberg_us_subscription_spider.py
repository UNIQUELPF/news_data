from news_scraper.spiders.usa.rss_feed_base import USARssFeedSpider


class USABloombergSpider(USARssFeedSpider):
    name = "usa_bloomberg_subscription"
    subscription_required = True
    access_note = "订阅/付费墙网站；仅采集可访问的公开正文，正文不全时需标记"
    source_name = "Bloomberg Economics"
    organization = "Bloomberg"
    allowed_domains = ["bloomberg.com"]
    section_name = "Economics"
    feed_urls = ["https://feeds.bloomberg.com/economics/news.rss"]
