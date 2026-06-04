from news_scraper.spiders.usa.business_media_base import USABusinessMediaSpider


class USAFortuneSpider(USABusinessMediaSpider):
    name = "usa_fortune"
    source_name = "Fortune"
    organization = "Fortune"
    allowed_domains = ["fortune.com"]
    fallback_content_selector = "article, .article-body, .paywall"
    section_name = "Business News"
    start_urls = [
        "https://fortune.com/section/news/",
        "https://fortune.com/section/finance/",
        "https://fortune.com/section/economy/",
    ]
    include_url_patterns = ("/20", "/section/news/", "/section/finance/", "/section/economy/")
