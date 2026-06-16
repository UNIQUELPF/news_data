from news_scraper.spiders.usa.rss_feed_base import USARssFeedSpider


class USAEPANewsSpider(USARssFeedSpider):
    name = "usa_epa_news"
    source_name = "Environmental Protection Agency News Releases"
    organization = "Environmental Protection Agency"
    allowed_domains = ["epa.gov", "news.google.com"]
    section_name = "News Releases"
    fetch_detail_pages = False
    feed_urls = [
        "https://news.google.com/rss/search?q=site%3Aepa.gov%2Fnewsreleases%20after%3A2026-01-01%20EPA&hl=en-US&gl=US&ceid=US:en"
    ]
    max_items = 5
