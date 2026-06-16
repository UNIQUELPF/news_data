from news_scraper.spiders.germany.germany_news_base import GermanyNewsBaseSpider


class GermanyDeutscheBoerseSpider(GermanyNewsBaseSpider):
    name = "germany_deutsche_boerse"
    source_name = "Deutsche Börse Press Releases"
    organization = "Deutsche Börse"
    language = "en"
    allowed_domains = ["deutsche-boerse.com", "www.deutsche-boerse.com"]
    section_name = "Press Releases"
    list_urls = ["https://www.deutsche-boerse.com/dbg-en/media/news-stories/press-releases"]
    include_url_patterns = ("/media/news-stories/press-releases/", "/dbg-en/")
    access_note = "无需订阅"
