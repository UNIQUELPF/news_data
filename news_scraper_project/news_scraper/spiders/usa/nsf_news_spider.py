from news_scraper.spiders.usa.gov_news_base import USAGovNewsSpider


class USANSFNewsSpider(USAGovNewsSpider):
    name = "usa_nsf_news"
    source_name = "National Science Foundation News"
    organization = "National Science Foundation"
    allowed_domains = ["nsf.gov"]
    section_name = "News"
    list_urls = ["https://www.nsf.gov/news"]
    include_url_patterns = ("/news/",)
    fallback_content_selector = "main, article, .field--name-body, .content"
