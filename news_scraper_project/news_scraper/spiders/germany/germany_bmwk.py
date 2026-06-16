from news_scraper.spiders.germany.germany_news_base import GermanyNewsBaseSpider


class GermanyBMWKSpider(GermanyNewsBaseSpider):
    name = "germany_bmwk"
    source_name = "Federal Ministry for Economic Affairs and Energy Media Room"
    organization = "Federal Ministry for Economic Affairs and Energy"
    language = "en"
    allowed_domains = ["bundeswirtschaftsministerium.de", "www.bundeswirtschaftsministerium.de"]
    section_name = "Media Room"
    feed_urls = [
        "https://news.google.com/rss/search?q=site%3Abundeswirtschaftsministerium.de%20after%3A2026-01-01&hl=en-US&gl=US&ceid=US:en"
    ]
    list_urls = [
        "https://www.bundeswirtschaftsministerium.de/SiteGlobals/BMWI/Forms/Listen/EN/Medienraum/Medienraum_Formular.html"
    ]
    include_url_patterns = ("/Redaktion/EN/", "/Navigation/EN/", "/Presse/")
    prefer_list_urls = True
    fetch_detail_pages = True
    access_note = "非订阅；原站启用Perfdrive/Captcha防护，普通HTTP无法稳定取得列表正文，站点限定RSS仅作入库兜底"
