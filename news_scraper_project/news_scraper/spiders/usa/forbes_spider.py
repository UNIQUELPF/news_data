from news_scraper.spiders.usa.rss_feed_base import USARssFeedSpider


class USAForbesSpider(USARssFeedSpider):
    name = 'usa_forbes'
    source_name = "Forbes Money"
    organization = "Forbes"
    allowed_domains = ['forbes.com']
    section_name = 'Money'
    feed_urls = [
        'https://www.forbes.com/sites/greatspeculations/feed/',
        'https://www.forbes.com/sites/simonmoore/feed/',
        'https://www.forbes.com/sites/digital-assets/feed/',
    ]
