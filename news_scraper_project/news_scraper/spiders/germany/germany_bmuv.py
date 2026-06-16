from news_scraper.spiders.germany.germany_news_base import GermanyNewsBaseSpider


class GermanyBMUVSpider(GermanyNewsBaseSpider):
    name = "germany_bmuv"
    source_name = "Bundesumweltministerium Pressemitteilungen"
    organization = "Bundesumweltministerium"
    allowed_domains = ["bundesumweltministerium.de", "www.bundesumweltministerium.de"]
    section_name = "Pressemitteilungen"
    list_urls = ["https://www.bundesumweltministerium.de/presse/pressemitteilungen"]
    feed_urls = ["https://www.bundesumweltministerium.de/umwelt.rss"]
    include_url_patterns = ("/presse/", "/meldung/", "/pressemitteilung")
    access_note = "无需订阅"
