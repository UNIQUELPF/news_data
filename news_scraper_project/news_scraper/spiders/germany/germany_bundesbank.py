from news_scraper.spiders.germany.germany_news_base import GermanyNewsBaseSpider


class GermanyBundesbankSpider(GermanyNewsBaseSpider):
    name = "germany_bundesbank"
    source_name = "Deutsche Bundesbank Press Releases"
    organization = "Deutsche Bundesbank"
    language = "en"
    allowed_domains = ["bundesbank.de", "www.bundesbank.de"]
    section_name = "Press Releases"
    feed_urls = [
        "https://www.bundesbank.de/service/rss/en/633306/feed.rss"
    ]
    list_urls = ["https://www.bundesbank.de/en/press/press-releases"]
    include_url_patterns = ("/en/press/press-releases/",)
    prefer_list_urls = True
    fetch_detail_pages = True
    access_note = "无需订阅；使用官方RSS获取原站详情链接并抓取正文HTML"
