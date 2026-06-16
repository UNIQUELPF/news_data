from news_scraper.spiders.usa.gov_news_base import USAGovNewsSpider


class USAOCCNewsSpider(USAGovNewsSpider):
    name = "usa_occ_news"
    source_name = "Office of the Comptroller of the Currency News Releases"
    organization = "Office of the Comptroller of the Currency"
    allowed_domains = ["occ.treas.gov", "occ.gov"]
    section_name = "News Release"
    list_urls = [
        "https://www.occ.gov/news-events/newsroom/news-issuances-by-year/news-releases/2026-news-releases.html"
    ]
    include_url_patterns = ("/news-issuances/news-releases/",)
    fallback_content_selector = "main, article, #main-content, .content"
