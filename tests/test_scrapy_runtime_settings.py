from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

import psycopg2

from news_scraper_project.news_scraper import settings as scrapy_settings
from news_scraper_project.news_scraper.pipelines import PostgresPipeline


class _FakeSettings:
    def __init__(self, *, enable_pipeline=True, postgres_settings=None):
        self.enable_pipeline = enable_pipeline
        self.postgres_settings = postgres_settings or {
            "dbname": "scrapy_db",
            "user": "user",
            "password": "pass",
            "host": "postgres",
            "port": 5432,
        }

    def getbool(self, name, default=False):
        if name == "ENABLE_POSTGRES_PIPELINE":
            return self.enable_pipeline
        return default

    def get(self, name, default=None):
        if name == "POSTGRES_SETTINGS":
            return self.postgres_settings
        return default


class ScrapyRuntimeSettingsTests(TestCase):
    def test_spider_modules_only_use_root_package(self):
        self.assertEqual(scrapy_settings.SPIDER_MODULES, ["news_scraper.spiders"])

    @patch("news_scraper_project.news_scraper.pipelines.psycopg2.connect")
    def test_pipeline_can_be_disabled_for_local_dry_runs(self, connect_mock):
        spider = SimpleNamespace(settings=_FakeSettings(enable_pipeline=False), logger=Mock())
        crawler = SimpleNamespace(spider=spider)
        pipeline = PostgresPipeline(crawler=crawler)

        pipeline.open_spider()

        self.assertFalse(pipeline.enabled)
        connect_mock.assert_not_called()
        spider.logger.info.assert_called_once()

    @patch("news_scraper_project.news_scraper.pipelines.psycopg2.connect")
    def test_pipeline_disables_itself_when_db_unavailable(self, connect_mock):
        connect_mock.side_effect = psycopg2.OperationalError("dns failed")
        spider = SimpleNamespace(settings=_FakeSettings(enable_pipeline=True), logger=Mock())
        crawler = SimpleNamespace(spider=spider)
        pipeline = PostgresPipeline(crawler=crawler)

        pipeline.open_spider()

        self.assertFalse(pipeline.enabled)
        spider.logger.error.assert_called_once()
