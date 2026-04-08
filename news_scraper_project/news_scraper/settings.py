import os

BOT_NAME = 'news_scraper'

# Dynamically discover all spider sub-packages (including nested ones like brics/)
spider_base_dir = os.path.join(os.path.dirname(__file__), 'spiders')

def _find_spider_modules(base_dir, base_pkg):
    """Recursively find all spider sub-packages."""
    modules = []
    for item in os.listdir(base_dir):
        item_path = os.path.join(base_dir, item)
        if os.path.isdir(item_path) and item != '__pycache__':
            pkg = f'{base_pkg}.{item}'
            modules.append(pkg)
            # Also check one level deeper (e.g. brics/china)
            modules.extend(_find_spider_modules(item_path, pkg))
    return modules

SPIDER_MODULES = ['news_scraper.spiders'] + _find_spider_modules(spider_base_dir, 'news_scraper.spiders')

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
