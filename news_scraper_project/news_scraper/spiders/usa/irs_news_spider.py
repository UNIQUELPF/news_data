from news_scraper.spiders.usa.rss_feed_base import USARssFeedSpider


class USAIRSNewsSpider(USARssFeedSpider):
    name = "usa_irs_news"
    source_name = "Internal Revenue Service Newsroom"
    organization = "Internal Revenue Service"
    allowed_domains = ["irs.gov", "news.google.com"]
    section_name = "Newsroom"
    fetch_detail_pages = False
    feed_urls = [
        "https://news.google.com/rss/search?q=site%3Airs.gov%2Fnewsroom%20after%3A2026-01-01%20IRS&hl=en-US&gl=US&ceid=US:en"
    ]
    max_items = 5
