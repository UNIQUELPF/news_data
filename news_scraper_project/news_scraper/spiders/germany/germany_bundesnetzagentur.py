from news_scraper.spiders.germany.germany_news_base import GermanyNewsBaseSpider


class GermanyBundesnetzagenturSpider(GermanyNewsBaseSpider):
    name = "germany_bundesnetzagentur"
    source_name = "Bundesnetzagentur Pressemitteilungen"
    organization = "Bundesnetzagentur"
    allowed_domains = ["bundesnetzagentur.de", "www.bundesnetzagentur.de"]
    section_name = "Pressemitteilungen"
    feed_urls = [
        "https://news.google.com/rss/search?q=site%3Abundesnetzagentur.de%20after%3A2026-01-01&hl=de&gl=DE&ceid=DE:de"
    ]
    list_urls = ["https://www.bundesnetzagentur.de/DE/Allgemeines/Presse/Pressemitteilungen/start.html"]
    include_url_patterns = ("/SharedDocs/Pressemitteilungen/",)
    prefer_list_urls = True
    fetch_detail_pages = True
    access_note = "无需订阅；优先原站列表与详情正文，站点限定RSS仅作补量兜底"
