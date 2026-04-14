import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRAPY_PROJECT_ROOT = PROJECT_ROOT / "news_scraper_project"
if str(SCRAPY_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRAPY_PROJECT_ROOT))

from news_scraper.spiders.argentina.argentina_ambito import ArgentinaAmbitoSpider
from news_scraper.spiders.brics.egypt.egypt_mubasher import EgyptMubasherSpider
from news_scraper.spiders.cambodia.base import CambodiaBaseSpider
from news_scraper.spiders.malaysia.enanyang_spider import EnanyangSpider


class _CambodiaTestSpider(CambodiaBaseSpider):
    name = "test_cambodia_spider"
    target_table = "test_cambodia_spider"


class SpiderIncrementalRuntimeTests(unittest.TestCase):
    @patch("news_scraper.spiders.cambodia.base.get_incremental_state")
    @patch("news_scraper.spiders.cambodia.base.psycopg2.connect")
    def test_cambodia_base_uses_incremental_helper(self, mock_connect, mock_state):
        mock_state.return_value = {
            "cutoff_date": CambodiaBaseSpider.default_cutoff.replace(year=2026, month=2, day=1),
            "scraped_urls": {"https://example.com/a"},
            "source": "unified",
        }
        connection = MagicMock()
        connection.cursor.return_value = MagicMock()
        mock_connect.return_value = connection

        spider = _CambodiaTestSpider()
        spider.settings = {
            "POSTGRES_SETTINGS": {
                "dbname": "db",
                "user": "user",
                "password": "pw",
                "host": "localhost",
                "port": 5432,
            }
        }

        cutoff = spider._init_db_and_get_cutoff()

        self.assertEqual(cutoff, mock_state.return_value["cutoff_date"])
        mock_state.assert_called_once()
        connection.commit.assert_called_once()
        connection.close.assert_called_once()

    @patch("news_scraper.spiders.cambodia.base.get_incremental_state")
    @patch("news_scraper.spiders.cambodia.base.psycopg2.connect")
    def test_cambodia_base_full_scan_skips_helper(self, mock_connect, mock_state):
        connection = MagicMock()
        connection.cursor.return_value = MagicMock()
        mock_connect.return_value = connection

        spider = _CambodiaTestSpider(full_scan="true")
        spider.settings = {
            "POSTGRES_SETTINGS": {
                "dbname": "db",
                "user": "user",
                "password": "pw",
                "host": "localhost",
                "port": 5432,
            }
        }

        cutoff = spider._init_db_and_get_cutoff()

        self.assertEqual(cutoff, spider.default_cutoff)
        mock_state.assert_not_called()

    @patch.object(EnanyangSpider, "init_db", return_value=None)
    @patch("news_scraper.spiders.malaysia.enanyang_spider.get_incremental_state")
    @patch("news_scraper.spiders.malaysia.enanyang_spider.psycopg2.connect")
    def test_enanyang_get_latest_db_date_uses_incremental_helper(
        self,
        mock_connect,
        mock_state,
        _mock_init_db,
    ):
        mock_state.return_value = {
            "cutoff_date": datetime(2026, 3, 1),
            "scraped_urls": set(),
            "source": "legacy",
        }
        cursor = MagicMock()
        cursor.fetchone.return_value = [True]
        connection = MagicMock()
        connection.cursor.return_value = cursor
        mock_connect.return_value = connection

        spider = EnanyangSpider(start_date="2026-01-01")
        spider.settings = {
            "POSTGRES_SETTINGS": {
                "dbname": "db",
                "user": "user",
                "password": "pw",
                "host": "localhost",
                "port": 5432,
            }
        }

        cutoff = spider.get_latest_db_date()

        self.assertEqual(cutoff, mock_state.return_value["cutoff_date"])
        mock_state.assert_called_once()
        connection.close.assert_called()

    @patch("news_scraper.spiders.argentina.argentina_ambito.get_incremental_state")
    @patch("news_scraper.spiders.argentina.argentina_ambito.psycopg2.connect")
    def test_argentina_spider_uses_incremental_helper(self, mock_connect, mock_state):
        mock_state.return_value = {
            "cutoff_date": datetime(2026, 4, 1),
            "scraped_urls": set(),
            "source": "unified",
        }
        connection = MagicMock()
        connection.cursor.return_value = MagicMock()
        mock_connect.return_value = connection

        spider = ArgentinaAmbitoSpider()
        spider.settings = {
            "POSTGRES_SETTINGS": {
                "dbname": "db",
                "user": "user",
                "password": "pw",
                "host": "localhost",
                "port": 5432,
            }
        }

        cutoff = spider._init_db_and_get_cutoff()

        self.assertEqual(cutoff, mock_state.return_value["cutoff_date"])
        mock_state.assert_called_once()
        connection.commit.assert_called_once()
        connection.close.assert_called_once()

    @patch("news_scraper.spiders.brics.egypt.egypt_mubasher.get_incremental_state")
    @patch("news_scraper.spiders.brics.egypt.egypt_mubasher.psycopg2.connect")
    def test_egypt_mubasher_init_db_loads_cutoff_and_seen_urls(self, mock_connect, mock_state):
        mock_state.return_value = {
            "cutoff_date": datetime(2026, 4, 2),
            "scraped_urls": {"https://example.com/article"},
            "source": "unified",
        }
        connection = MagicMock()
        connection.cursor.return_value = MagicMock()
        mock_connect.return_value = connection

        spider = EgyptMubasherSpider()
        spider.settings = {
            "POSTGRES_SETTINGS": {
                "dbname": "db",
                "user": "user",
                "password": "pw",
                "host": "localhost",
                "port": 5432,
            }
        }

        spider._init_db()

        self.assertEqual(spider.cutoff_date, mock_state.return_value["cutoff_date"])
        self.assertEqual(spider.seen_urls, mock_state.return_value["scraped_urls"])
        mock_state.assert_called_once()
        connection.commit.assert_called_once()
        connection.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
