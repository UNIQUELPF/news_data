from news_scraper.spiders.germany.germany_news_base import GermanyNewsBaseSpider


class GermanyAuswaertigesAmtSpider(GermanyNewsBaseSpider):
    name = "germany_auswaertiges_amt"
    source_name = "Federal Foreign Office News"
    organization = "Federal Foreign Office"
    language = "en"
    allowed_domains = ["auswaertiges-amt.de", "www.auswaertiges-amt.de"]
    section_name = "News"
    feed_urls = [
        "https://news.google.com/rss/search?q=site%3Aauswaertiges-amt.de%2Fen%2Fnewsroom%20after%3A2026-01-01&hl=en-US&gl=US&ceid=US:en"
    ]
    list_urls = [
        "https://www.auswaertiges-amt.de/ajax/json-filterlist/en/newsroom/news/300960-300960",
        "https://www.auswaertiges-amt.de/en/newsroom/news",
    ]
    include_url_patterns = ("/en/newsroom/news/",)
    prefer_list_urls = True
    fetch_detail_pages = True
    access_note = "无需订阅；优先原站列表与详情正文，站点限定RSS仅作补量兜底"
