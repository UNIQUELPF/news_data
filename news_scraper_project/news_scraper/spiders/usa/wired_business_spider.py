from news_scraper.spiders.usa.rss_feed_base import USARssFeedSpider


class USAWiredBusinessSpider(USARssFeedSpider):
    name = "usa_wired_business"
    source_name = "Wired Business"
    organization = "Wired"
    allowed_domains = ["wired.com"]
    section_name = "Business"
    feed_urls = ["https://www.wired.com/feed/category/business/latest/rss"]
