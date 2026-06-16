from news_scraper.spiders.usa.rss_feed_base import USARssFeedSpider


class USADHSNewsSpider(USARssFeedSpider):
    name = "usa_dhs_news"
    source_name = "Department of Homeland Security News"
    organization = "Department of Homeland Security"
    allowed_domains = ["dhs.gov", "news.google.com"]
    section_name = "News Updates"
    fetch_detail_pages = False
    feed_urls = [
        "https://news.google.com/rss/search?q=site%3Adhs.gov%2Fnews%20after%3A2026-01-01%20DHS&hl=en-US&gl=US&ceid=US:en"
    ]
    max_items = 5
