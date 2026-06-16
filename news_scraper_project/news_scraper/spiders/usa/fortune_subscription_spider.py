from news_scraper.spiders.usa.business_media_base import USABusinessMediaSpider


class USAFortuneSpider(USABusinessMediaSpider):
    name = "usa_fortune_subscription"
    subscription_required = True
    access_note = "订阅/付费墙网站；仅采集可访问的公开正文，正文不全时需标记"
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
