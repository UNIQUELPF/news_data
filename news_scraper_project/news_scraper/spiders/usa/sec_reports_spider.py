from news_scraper.spiders.usa.rss_feed_base import USARssFeedSpider


class USASECReportsSpider(USARssFeedSpider):
    name = "usa_sec_reports"
    source_name = "SEC Reports"
    organization = "U.S. Securities and Exchange Commission"
    allowed_domains = ["sec.gov"]
    section_name = "Reports"
    feed_urls = ["https://www.sec.gov/news/pressreleases.rss"]
