from news_scraper.spiders.usa.rss_feed_base import USARssFeedSpider


class USACNETSpider(USARssFeedSpider):
    name = "usa_cnet"
    source_name = "CNET Business Technology"
    organization = "CNET"
    allowed_domains = ["cnet.com"]
    section_name = "Business Technology"
    feed_urls = ["https://www.cnet.com/rss/news/"]
