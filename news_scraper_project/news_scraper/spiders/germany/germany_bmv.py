from news_scraper.spiders.germany.germany_news_base import GermanyNewsBaseSpider


class GermanyBMVSpider(GermanyNewsBaseSpider):
    name = "germany_bmv"
    source_name = "Bundesministerium für Verkehr Press Releases"
    organization = "Bundesministerium für Verkehr"
    allowed_domains = ["bmv.de", "www.bmv.de"]
    section_name = "Press Releases"
    feed_urls = [
        "https://news.google.com/rss/search?q=site%3Abmv.de%20after%3A2026-01-01&hl=de&gl=DE&ceid=DE:de"
    ]
    list_urls = [
        "https://www.bmv.de/SiteGlobals/Forms/Suche/DE/Expertensuche_Formular.html?nn=76092&documentType_=PressRelease"
    ]
    include_url_patterns = ("/SharedDocs/DE/Pressemitteilungen/",)
    prefer_list_urls = True
    fetch_detail_pages = True
    access_note = "无需订阅；优先原站列表与详情正文，站点限定RSS仅作补量兜底"
