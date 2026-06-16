from news_scraper.spiders.germany.germany_news_base import GermanyNewsBaseSpider


class GermanyBVLSpider(GermanyNewsBaseSpider):
    name = "germany_bvl"
    source_name = "BVL Pressemitteilungen"
    organization = "Bundesamt für Verbraucherschutz und Lebensmittelsicherheit"
    allowed_domains = ["bvl.bund.de", "www.bvl.bund.de"]
    section_name = "Pressemitteilungen"
    feed_urls = [
        "https://news.google.com/rss/search?q=site%3Abvl.bund.de%20after%3A2026-01-01&hl=de&gl=DE&ceid=DE:de"
    ]
    list_urls = ["https://www.bvl.bund.de/DE/Service/02_Presse/02_pressemitteilungen/pressemitteilungen_node.html"]
    include_url_patterns = ("/SharedDocs/Pressemitteilungen/",)
    prefer_list_urls = True
    fetch_detail_pages = True
    access_note = "无需订阅；优先原站列表与详情正文，站点限定RSS仅作补量兜底"
