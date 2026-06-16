from news_scraper.spiders.germany.germany_news_base import GermanyNewsBaseSpider


class GermanyBundeskartellamtSpider(GermanyNewsBaseSpider):
    name = "germany_bundeskartellamt"
    source_name = "Bundeskartellamt Press Releases"
    organization = "Bundeskartellamt"
    language = "en"
    allowed_domains = ["bundeskartellamt.de", "www.bundeskartellamt.de"]
    section_name = "Press Releases"
    feed_urls = [
        "https://news.google.com/rss/search?q=site%3Abundeskartellamt.de%20after%3A2026-01-01%20Bundeskartellamt&hl=en-US&gl=US&ceid=US:en"
    ]
    list_urls = [
        "https://www.bundeskartellamt.de/SiteGlobals/Forms/Suche/EN/Expertensuche_Formular.html?nn=50282&sortOrder=dateOfIssue_dt+desc&cl2Categories_CategorizedFormat=pressemeldungen_aktuelles&pageLocale=en"
    ]
    include_url_patterns = ("/SharedDocs/Meldung/EN/Pressemitteilungen/",)
    prefer_list_urls = True
    fetch_detail_pages = True
    access_note = "无需订阅；优先原站列表与详情正文，站点限定RSS仅作补量兜底"
