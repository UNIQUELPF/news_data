from news_scraper.spiders.usa.rss_feed_base import USARssFeedSpider


class USAWhiteHouseNewsSpider(USARssFeedSpider):
    name = "usa_whitehouse_news"
    source_name = "The White House News"
    organization = "The White House"
    allowed_domains = ["whitehouse.gov"]
    section_name = "News"
    feed_urls = ["https://www.whitehouse.gov/news/feed/"]
