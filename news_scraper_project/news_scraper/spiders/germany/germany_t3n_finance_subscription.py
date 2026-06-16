from news_scraper.spiders.germany.germany_news_base import GermanyNewsBaseSpider


class GermanyT3NFinanceSpider(GermanyNewsBaseSpider):
    name = "germany_t3n_finance_subscription"
    source_name = "t3n Finance"
    organization = "t3n"
    allowed_domains = ["t3n.de"]
    section_name = "Finance"
    feed_urls = ["https://t3n.de/tag/finance/rss.xml"]
    subscription_required = True
    access_note = "用户标记为订阅站；采集公开RSS与可访问详情"
