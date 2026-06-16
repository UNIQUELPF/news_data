from news_scraper.spiders.usa.rss_feed_base import USARssFeedSpider


class USAWSJSpider(USARssFeedSpider):
    name = "usa_wsj_subscription"
    subscription_required = True
    access_note = "订阅/付费墙网站；仅采集可访问的公开正文，正文不全时需标记"
    source_name = "Wall Street Journal Business"
    organization = "Wall Street Journal"
    allowed_domains = ["wsj.com"]
    section_name = "Business"
    feed_urls = [
        "https://news.google.com/rss/search?q=site%3Awsj.com%2Farticles%20business%20finance%20market%20WSJ&hl=en-US&gl=US&ceid=US%3Aen",
    ]
