from news_scraper.spiders.usa.rss_feed_base import USARssFeedSpider


class USAZDNetBusinessSpider(USARssFeedSpider):
    name = "usa_zdnet_business"
    source_name = "ZDNET Business"
    organization = "ZDNET"
    allowed_domains = ["zdnet.com"]
    section_name = "Business Technology"
    feed_urls = ["https://www.zdnet.com/news/rss.xml"]
