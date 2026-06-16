from news_scraper.spiders.usa.rss_feed_base import USARssFeedSpider


class UkMoneyweekSpider(USARssFeedSpider):
    """
    MoneyWeek UK Economy spider.

    MoneyWeek uses a paywall (HTTP 451/403 from Jina Reader) and has
    no dates on listing pages. Strategy: use Google News RSS to discover
    recent articles with dates, then fetch detail pages with standard HTTP.
    """
    name = "uk_moneyweek"
    allowed_domains = ["moneyweek.com", "news.google.com"]
    source_timezone = "Europe/London"

    country_code = "GBR"
    country = "英国"
    language = "en"

    # Override USA defaults from the base class
    dateparser_settings = {"DATE_ORDER": "DMY"}
    section_name = "UK Economy"
    organization = "MoneyWeek"

    # Google News RSS feeds for MoneyWeek UK Economy content
    feed_urls = [
        "https://news.google.com/rss/search?q=site:moneyweek.com+economy&hl=en-GB&gl=GB&ceid=GB:en",
        "https://news.google.com/rss/search?q=moneyweek+uk+economy+finance&hl=en-GB&gl=GB&ceid=GB:en",
    ]

    fetch_detail_pages = True
    fallback_content_selector = (
        "div.article__body, div.article-body, article, main, .content"
    )
    max_items = 20
