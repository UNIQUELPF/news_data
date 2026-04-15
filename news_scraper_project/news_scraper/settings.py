import os

BOT_NAME = "news_scraper"

# Let Scrapy discover spiders from the package root. Explicitly listing nested
# sub-packages causes the same spider modules to be imported multiple times.
SPIDER_MODULES = ["news_scraper.spiders"]

NEWSPIDER_MODULE = "news_scraper.spiders"

ROBOTSTXT_OBEY = False

# Optimized for speed while avoiding IP bans
DOWNLOAD_DELAY = 0.5
CONCURRENT_REQUESTS = 8
CONCURRENT_REQUESTS_PER_DOMAIN = 4
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1
AUTOTHROTTLE_MAX_DELAY = 10
AUTOTHROTTLE_TARGET_CONCURRENCY = 2.0

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

POSTGRES_SETTINGS = {
    "dbname": os.getenv("POSTGRES_DB", "scrapy_db"),
    "user": os.getenv("POSTGRES_USER", "your_user"),
    "password": os.getenv("POSTGRES_PASSWORD", "your_password"),
    "host": os.getenv("POSTGRES_HOST", "postgres"),
    "port": int(os.getenv("POSTGRES_PORT", "5432")),
}

ITEM_PIPELINES = {
    "news_scraper.pipelines.PostgresPipeline": 300,
}

ENABLE_UNIFIED_PIPELINE = os.getenv("ENABLE_UNIFIED_PIPELINE", "1") == "1"
ENABLE_LEGACY_TABLES = os.getenv("ENABLE_LEGACY_TABLES", "1") == "1"
ENABLE_POSTGRES_PIPELINE = os.getenv("ENABLE_POSTGRES_PIPELINE", "1") == "1"

DOWNLOADER_MIDDLEWARES = {
    "news_scraper.middlewares.CurlCffiMiddleware": 101,
    "news_scraper.middlewares.BatchDelayMiddleware": 600,
}

TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
FEED_EXPORT_ENCODING = "utf-8"
TELNETCONSOLE_ENABLED = os.getenv("TELNETCONSOLE_ENABLED", "0") == "1"

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
