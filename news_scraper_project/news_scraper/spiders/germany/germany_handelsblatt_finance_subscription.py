from news_scraper.spiders.germany.germany_news_base import GermanyNewsBaseSpider


class GermanyHandelsblattFinanceSpider(GermanyNewsBaseSpider):
    name = "germany_handelsblatt_finance_subscription"
    source_name = "Handelsblatt Finanzen"
    organization = "Handelsblatt"
    allowed_domains = ["handelsblatt.com", "www.handelsblatt.com"]
    section_name = "Finance"
    list_urls = ["https://www.handelsblatt.com/finanzen/"]
    include_url_patterns = ("/finanzen/",)
    subscription_required = True
    access_note = "用户标记为订阅站；详情页可能有付费墙，仅采集可访问正文"
    fallback_content_selector = "main, article, .vhb-article, .article-content"
