from news_scraper.spiders.usa.rss_feed_base import USARssFeedSpider


class USABarronsSpider(USARssFeedSpider):
    name = "usa_barrons_subscription"
    subscription_required = True
    access_note = "订阅/付费墙网站；仅采集可访问的公开正文，正文不全时需标记"
    source_name = "Barron's Economy and Policy"
    organization = "Barron's"
    allowed_domains = ["barrons.com"]
    section_name = "Economy and Policy"
    feed_urls = [
        "https://news.google.com/rss/search?q=site%3Abarrons.com%2Farticles%20economy%20policy%20markets%20Barron%27s&hl=en-US&gl=US&ceid=US%3Aen"
    ]
