from news_scraper.spiders.usa.rss_feed_base import USARssFeedSpider


class USATheInformationFinanceSpider(USARssFeedSpider):
    name = "usa_theinformation_finance_subscription"
    subscription_required = True
    access_note = "订阅/付费墙网站；仅采集可访问的公开正文，正文不全时需标记"
    source_name = "The Information Finance"
    organization = "The Information"
    allowed_domains = ["theinformation.com"]
    section_name = "Finance"
    feed_urls = [
        "https://news.google.com/rss/search?q=site%3Atheinformation.com%2Farticles%20finance%20%22The%20Information%22&hl=en-US&gl=US&ceid=US%3Aen"
    ]
