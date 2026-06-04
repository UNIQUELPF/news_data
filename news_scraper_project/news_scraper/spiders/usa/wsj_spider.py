from news_scraper.spiders.usa.rss_feed_base import USARssFeedSpider


class USAWSJSpider(USARssFeedSpider):
    name = "usa_wsj"
    source_name = "Wall Street Journal Business"
    organization = "Wall Street Journal"
    allowed_domains = ["wsj.com"]
    section_name = "Business"
    feed_urls = [
        "https://news.google.com/rss/search?q=site%3Awsj.com%2Farticles%20business%20finance%20market%20WSJ&hl=en-US&gl=US&ceid=US%3Aen",
    ]
