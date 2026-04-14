from datetime import datetime
from unittest import TestCase
from unittest.mock import patch

from news_scraper_project.news_scraper.utils import get_incremental_state


class SpiderUtilsTests(TestCase):
    @patch("news_scraper_project.news_scraper.utils._get_db_connection")
    def test_get_incremental_state_accepts_missing_settings(self, connection_mock):
        connection_mock.side_effect = RuntimeError("db unavailable")

        state = get_incremental_state(
            None,
            spider_name="demo_spider",
            table_name="demo_table",
            default_cutoff=datetime(2026, 1, 1),
        )

        self.assertEqual(state["cutoff_date"], datetime(2026, 1, 1))
        self.assertEqual(state["scraped_urls"], set())
        self.assertEqual(state["source"], "default")
