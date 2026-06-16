from news_scraper.spiders.usa.rss_feed_base import USARssFeedSpider


class USACFPBNewsSpider(USARssFeedSpider):
    name = "usa_cfpb_news"
    source_name = "Consumer Financial Protection Bureau Newsroom"
    organization = "Consumer Financial Protection Bureau"
    allowed_domains = ["consumerfinance.gov", "news.google.com"]
    section_name = "Press Release"
    fetch_detail_pages = False
    feed_urls = [
        "https://news.google.com/rss/search?q=site%3Aconsumerfinance.gov%2Fabout-us%2Fnewsroom%20after%3A2026-01-01&hl=en-US&gl=US&ceid=US:en"
    ]
    max_items = 5
