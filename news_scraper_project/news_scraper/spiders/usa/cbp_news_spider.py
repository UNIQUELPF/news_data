from news_scraper.spiders.usa.rss_feed_base import USARssFeedSpider


class USACBPNewsSpider(USARssFeedSpider):
    name = "usa_cbp_news"
    source_name = "U.S. Customs and Border Protection Newsroom"
    organization = "U.S. Customs and Border Protection"
    allowed_domains = ["cbp.gov", "news.google.com"]
    section_name = "Newsroom"
    fetch_detail_pages = False
    feed_urls = [
        "https://news.google.com/rss/search?q=site%3Acbp.gov%2Fnewsroom%20after%3A2026-01-01%20CBP&hl=en-US&gl=US&ceid=US:en"
    ]
    max_items = 5
