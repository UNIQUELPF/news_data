import re
import unittest
from pathlib import Path

SPIDERS_DIR = Path("news_scraper_project/news_scraper/spiders")
LEGACY_MAX_PATTERN = re.compile(r"SELECT MAX\(publish_time\) FROM")
INCREMENTAL_HELPER_PATTERN = re.compile(r"get_incremental_state\s*\(")


class SpiderIncrementalMigrationTests(unittest.TestCase):
    def test_spiders_do_not_use_legacy_max_publish_time_query(self):
        offenders = []

        for path in SPIDERS_DIR.rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="ignore")
            if LEGACY_MAX_PATTERN.search(text):
                offenders.append(str(path))

        self.assertEqual(
            offenders,
            [],
            f"legacy incremental SQL still present in spiders: {offenders}",
        )

    def test_spiders_use_incremental_helper_somewhere(self):
        users = 0

        for path in SPIDERS_DIR.rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="ignore")
            if INCREMENTAL_HELPER_PATTERN.search(text):
                users += 1

        self.assertGreater(
            users,
            0,
            "expected spiders to use get_incremental_state after migration",
        )


if __name__ == "__main__":
    unittest.main()
