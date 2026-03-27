import os

BOT_NAME = 'news_scraper'

SPIDER_MODULES = [
    'news_scraper.spiders',
    'news_scraper.spiders.serbia',
    'news_scraper.spiders.azerbaijan',
    'news_scraper.spiders.albania',
    'news_scraper.spiders.algeria',
    'news_scraper.spiders.argentina',
    'news_scraper.spiders.austria',
    'news_scraper.spiders.ireland',
    'news_scraper.spiders.oman',
    'news_scraper.spiders.kazakhstan',
    'news_scraper.spiders.brics.china',
    'news_scraper.spiders.brics.russia',
    'news_scraper.spiders.brics.india',
    'news_scraper.spiders.brics.brazil',
    'news_scraper.spiders.brics.south_africa',
    'news_scraper.spiders.brics.egypt',
    'news_scraper.spiders.brics.ethiopia',
    'news_scraper.spiders.brics.iran',
    'news_scraper.spiders.brics.uae',
    'news_scraper.spiders.brics.saudi_arabia',
    'news_scraper.spiders.brics.indonesia',
]
NEWSPIDER_MODULE = 'news_scraper.spiders'

ROBOTSTXT_OBEY = False

# Optimized for speed while avoiding IP bans
DOWNLOAD_DELAY = 0.5
CONCURRENT_REQUESTS = 32
CONCURRENT_REQUESTS_PER_DOMAIN = 16
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1
AUTOTHROTTLE_MAX_DELAY = 10
AUTOTHROTTLE_TARGET_CONCURRENCY = 8.0

USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'

POSTGRES_SETTINGS = {
    'dbname': os.getenv('POSTGRES_DB', 'scrapy_db'),
    'user': os.getenv('POSTGRES_USER', 'your_user'),
    'password': os.getenv('POSTGRES_PASSWORD', 'your_password'),
    'host': os.getenv('POSTGRES_HOST', 'localhost'),
    'port': int(os.getenv('POSTGRES_PORT', '5433'))
}

ITEM_PIPELINES = {
    'news_scraper.pipelines.PostgresPipeline': 300,
}

DOWNLOADER_MIDDLEWARES = {
    'news_scraper.middlewares.CurlCffiMiddleware': 101,
    'news_scraper.middlewares.BatchDelayMiddleware': 600,
}

TWISTED_REACTOR = 'twisted.internet.asyncioreactor.AsyncioSelectorReactor'
FEED_EXPORT_ENCODING = 'utf-8'

# Playwright configuration
PLAYWRIGHT_BROWSER_TYPE = "chromium"
PLAYWRIGHT_LAUNCH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-dev-shm-usage",
    "--no-sandbox",
]
