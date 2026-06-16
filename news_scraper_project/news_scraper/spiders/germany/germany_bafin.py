from news_scraper.spiders.germany.germany_news_base import GermanyNewsBaseSpider


class GermanyBafinSpider(GermanyNewsBaseSpider):
    name = "germany_bafin"
    source_name = "BaFin Consumer News"
    organization = "BaFin"
    language = "en"
    allowed_domains = ["bafin.de", "www.bafin.de"]
    section_name = "Consumer News"
    feed_urls = [
        "https://news.google.com/rss/search?q=site%3Abafin.de%2FEN%20BaFin%20after%3A2026-01-01&hl=en-US&gl=US&ceid=US:en"
    ]
    list_urls = ["https://www.bafin.de/EN/verbraucherinnen-verbraucher/news-warnungen/verbrauchernews/verbrauchernews_node_en.html"]
    include_url_patterns = ("/EN/", "/SharedDocs/")
    prefer_list_urls = True
    fetch_detail_pages = True
    access_note = "无需订阅；优先原站列表与详情正文，站点限定RSS仅作补量兜底"
