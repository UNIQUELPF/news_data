from news_scraper.spiders.usa.rss_feed_base import USARssFeedSpider


class USATheInformationFinanceSpider(USARssFeedSpider):
    name = "usa_theinformation_finance"
    source_name = "The Information Finance"
    organization = "The Information"
    allowed_domains = ["theinformation.com"]
    section_name = "Finance"
    feed_urls = [
        "https://news.google.com/rss/search?q=site%3Atheinformation.com%2Farticles%20finance%20%22The%20Information%22&hl=en-US&gl=US&ceid=US%3Aen"
    ]
