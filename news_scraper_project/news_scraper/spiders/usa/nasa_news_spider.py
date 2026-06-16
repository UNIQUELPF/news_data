from news_scraper.spiders.usa.rss_feed_base import USARssFeedSpider


class USANASANewsSpider(USARssFeedSpider):
    name = "usa_nasa_news"
    source_name = "NASA News"
    organization = "National Aeronautics and Space Administration"
    allowed_domains = ["nasa.gov"]
    section_name = "News"
    feed_urls = ["https://www.nasa.gov/news-release/feed/"]
