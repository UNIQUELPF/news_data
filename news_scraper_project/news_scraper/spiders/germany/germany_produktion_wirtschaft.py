from news_scraper.spiders.germany.germany_news_base import GermanyNewsBaseSpider


class GermanyProduktionWirtschaftSpider(GermanyNewsBaseSpider):
    name = "germany_produktion_wirtschaft"
    source_name = "Produktion Wirtschaft"
    organization = "Produktion"
    allowed_domains = ["produktion.de", "www.produktion.de"]
    section_name = "Wirtschaft"
    list_urls = ["https://www.produktion.de/wirtschaft"]
    include_url_patterns = ("/wirtschaft/",)
    access_note = "无需订阅"
