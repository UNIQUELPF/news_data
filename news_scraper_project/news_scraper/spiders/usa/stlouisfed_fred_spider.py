from news_scraper.spiders.usa.rss_feed_base import USARssFeedSpider


class USAStLouisFedFREDSpider(USARssFeedSpider):
    name = "usa_stlouisfed_fred"
    source_name = "FRED Announcements"
    organization = "Federal Reserve Bank of St. Louis"
    allowed_domains = ["news.research.stlouisfed.org"]
    section_name = "FRED Announcements"
    feed_urls = ["https://news.research.stlouisfed.org/category/fred-announcements/feed/"]
