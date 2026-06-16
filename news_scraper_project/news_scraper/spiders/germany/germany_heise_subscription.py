from news_scraper.spiders.germany.germany_news_base import GermanyNewsBaseSpider


class GermanyHeiseSpider(GermanyNewsBaseSpider):
    name = "germany_heise_subscription"
    source_name = "Heise Newsticker"
    organization = "Heise"
    allowed_domains = ["heise.de", "www.heise.de"]
    section_name = "Technology News"
    feed_urls = ["https://www.heise.de/rss/heise-atom.xml"]
    subscription_required = True
    access_note = "用户标记为订阅站；采集公开RSS与可访问详情"
