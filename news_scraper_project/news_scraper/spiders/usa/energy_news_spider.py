from news_scraper.spiders.usa.rss_feed_base import USARssFeedSpider


class USAEnergyNewsSpider(USARssFeedSpider):
    name = "usa_energy_news"
    source_name = "U.S. Department of Energy News"
    organization = "U.S. Department of Energy"
    allowed_domains = ["energy.gov", "news.google.com"]
    section_name = "News"
    fetch_detail_pages = False
    feed_urls = [
        "https://news.google.com/rss/search?q=site%3Aenergy.gov%2Farticles%20after%3A2026-01-01%20Department%20of%20Energy&hl=en-US&gl=US&ceid=US:en"
    ]
    max_items = 5
