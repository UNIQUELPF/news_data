from news_scraper.spiders.usa.rss_feed_base import USARssFeedSpider


class USAInvestopediaSpider(USARssFeedSpider):
    name = "usa_investopedia"
    source_name = "Investopedia News"
    organization = "Investopedia"
    allowed_domains = ["investopedia.com"]
    section_name = "Financial News"
    feed_urls = [
        "https://news.google.com/rss/search?q=site%3Ainvestopedia.com%20stock%20market%20investopedia&hl=en-US&gl=US&ceid=US%3Aen",
        "https://news.google.com/rss/search?q=site%3Ainvestopedia.com%20economy%20markets&hl=en-US&gl=US&ceid=US%3Aen",
    ]
