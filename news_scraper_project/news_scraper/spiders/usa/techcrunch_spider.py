from news_scraper.spiders.usa.business_media_base import USABusinessMediaSpider


class USATechCrunchSpider(USABusinessMediaSpider):
    name = "usa_techcrunch"
    source_name = "TechCrunch"
    organization = "TechCrunch"
    allowed_domains = ["techcrunch.com"]
    fallback_content_selector = "article, .article-content, .entry-content"
    section_name = "Technology Business"
    start_urls = [
        "https://techcrunch.com/latest/",
        "https://techcrunch.com/category/fintech/",
        "https://techcrunch.com/category/venture/",
        "https://techcrunch.com/category/startups/",
    ]
    include_url_patterns = ("/20",)
