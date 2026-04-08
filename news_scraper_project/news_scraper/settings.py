import os

BOT_NAME = 'news_scraper'

# Dynamically discover all spider sub-packages to build SPIDER_MODULES
spider_base_dir = os.path.join(os.path.dirname(__file__), 'spiders')
sub_modules = [
    f'news_scraper.spiders.{d}' 
    for d in os.listdir(spider_base_dir) 
    if os.path.isdir(os.path.join(spider_base_dir, d)) and d != '__pycache__'
]

SPIDER_MODULES = [
    'news_scraper.spiders',
] + sub_modules




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
    'host': os.getenv('POSTGRES_HOST', 'postgres'),
    'port': int(os.getenv('POSTGRES_PORT', '5432'))
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

DOWNLOAD_HANDLERS = {
    "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}

