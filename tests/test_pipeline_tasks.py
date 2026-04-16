import unittest
from unittest.mock import MagicMock, PropertyMock, patch

from pipeline.tasks.crawl import _extract_items_scraped
from pipeline.tasks.embed import _chunk_text, embed_article
from pipeline.domestic_taxonomy import (
    infer_domestic_category,
    infer_domestic_location,
    normalize_domestic_category,
    split_organization_and_company,
)
from pipeline.tasks.translate import _is_same_language_passthrough, _placeholder_summary, _placeholder_translate_text, translate_article


class PipelineTaskHelpersTest(unittest.TestCase):
    def test_extract_items_scraped_from_stats_output(self):
        stdout = "Stats: {'item_scraped_count': 24, 'finish_reason': 'closespider_pagecount'}"
        self.assertEqual(_extract_items_scraped(stdout), 24)
        self.assertEqual(_extract_items_scraped("no stats"), 0)

    def test_chunk_text_handles_empty_value(self):
        self.assertEqual(_chunk_text(None), [])
        self.assertEqual(_chunk_text(""), [])

    def test_chunk_text_compacts_whitespace_and_splits_by_size(self):
        chunks = _chunk_text("A   B\n\nC\tD", chunk_size=3)
        self.assertEqual(chunks, ["A B", " C ", "D"])

    def test_placeholder_translate_text(self):
        self.assertIsNone(_placeholder_translate_text(None, "zh-CN"))
        self.assertEqual(
            _placeholder_translate_text("OpenAI expands Europe team", "zh-CN"),
            "[zh-CN placeholder] OpenAI expands Europe team",
        )

    def test_placeholder_summary_compacts_and_truncates(self):
        long_text = "word " * 100
        summary = _placeholder_summary(long_text, "zh-CN")
        self.assertTrue(summary.startswith("[zh-CN summary placeholder] "))
        self.assertTrue(summary.endswith("..."))
        self.assertLessEqual(len(summary), len("[zh-CN summary placeholder] ") + 280)

    def test_same_language_passthrough_detects_chinese(self):
        self.assertTrue(_is_same_language_passthrough("zh-CN", "zh-CN"))
        self.assertTrue(_is_same_language_passthrough("zh", "zh-TW"))
        self.assertFalse(_is_same_language_passthrough("en", "zh-CN"))

    def test_normalize_category_maps_domestic_aliases(self):
        self.assertEqual(normalize_domestic_category("金融"), "经济")
        self.assertEqual(normalize_domestic_category("法律"), "法规")
        self.assertEqual(normalize_domestic_category("文化"), "社会")
        self.assertEqual(normalize_domestic_category("环境"), "环境")
        self.assertEqual(normalize_domestic_category(None), None)

    def test_infer_domestic_category_uses_keywords_and_section(self):
        self.assertEqual(infer_domestic_category("三部门发布价格行为规则", None, None, "news_headline"), "法规")
        self.assertEqual(infer_domestic_category("量子科技赛道融资增长", None, "finance", "headline"), "科技")
        self.assertEqual(infer_domestic_category("铁路发送旅客创新高", None, "finance", "headline"), "经济")

    def test_infer_domestic_location_and_org_company_split(self):
        self.assertEqual(infer_domestic_location("深圳发布低空经济新政", None), ("广东", "深圳"))
        self.assertEqual(split_organization_and_company("中国汽车工业协会"), ("中国汽车工业协会", None))
        self.assertEqual(split_organization_and_company("华创证券,南方基金"), (None, "华创证券,南方基金"))

)

    @patch("pipeline.tasks.translate.get_db_connection")
    @patch("pipeline.tasks.translate._fetch_article")
    @patch("pipeline.tasks.translate._upsert_translation")
    @patch("pipeline.tasks.translate._set_translation_status")
    @patch("pipeline.tasks.translate.is_llm_enabled")
    def test_translate_article_placeholder_completed(
        self,
        mock_llm_enabled,
        mock_set_status,
        mock_upsert_translation,
        mock_fetch_article,
        mock_connection_factory,
    ):
        mock_llm_enabled.return_value = False
        mock_fetch_article.return_value = (5, "Title", "Body content", "en", "pending", "world", "headline")
        connection = MagicMock()
        connection.cursor.return_value = MagicMock()
        mock_connection_factory.return_value = connection

        result = translate_article(article_id=5, target_language="zh-CN")

        self.assertEqual(result, {
            "article_id": 5,
            "target_language": "zh-CN",
            "status": "completed",
            "mode": "placeholder",
        })
        self.assertEqual(mock_set_status.call_args_list[0].args[2], "processing")
        self.assertEqual(mock_set_status.call_args_list[-1].args[2], "completed")
        mock_upsert_translation.assert_called_once()
        connection.commit.assert_called_once()
        connection.close.assert_called_once()

    @patch("pipeline.tasks.translate.get_db_connection")
    @patch("pipeline.tasks.translate._fetch_article")
    @patch("pipeline.tasks.translate._upsert_translation_with_translator")
    @patch("pipeline.tasks.translate._set_translation_status")
    @patch("pipeline.tasks.translate.is_llm_enabled")
    @patch("pipeline.tasks.translate.extract_domestic_article_metadata")
    def test_translate_article_passthrough_for_chinese_source(
        self,
        mock_extract_domestic_article_metadata,
        mock_llm_enabled,
        mock_set_status,
        mock_upsert_translation_with_translator,
        mock_fetch_article,
        mock_connection_factory,
    ):
        mock_llm_enabled.return_value = True
        mock_extract_domestic_article_metadata.return_value = {
            "category": "经济",
            "province": "北京",
            "city": "北京",
            "involved_companies": "中国汽车工业协会",
            "confidence": 0.93,
        }
        mock_fetch_article.return_value = (7, "中文标题", "中文正文", "zh-CN", "pending", "finance", "headline")
        connection = MagicMock()
        cursor = MagicMock()
        connection.cursor.return_value = cursor
        mock_connection_factory.return_value = connection

        result = translate_article(article_id=7, target_language="zh-CN")

        self.assertEqual(result, {
            "article_id": 7,
            "target_language": "zh-CN",
            "status": "completed",
            "mode": "passthrough",
        })
        mock_upsert_translation_with_translator.assert_called_once_with(
            cursor,
            7,
            "zh-CN",
            "中文标题",
            None,
            "中文正文",
            "source-original",
        )
        cursor.execute.assert_any_call(
            """
                    UPDATE articles
                    SET category = COALESCE(%s, category),
                        province = COALESCE(%s, province),
                        city = COALESCE(%s, city),
                        company = COALESCE(%s, company),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
            ("经济", "北京", "北京", "中国汽车工业协会", 7),
        )
        self.assertEqual(mock_set_status.call_args_list[0].args[2], "processing")
        self.assertEqual(mock_set_status.call_args_list[-1].args[2], "completed")
        connection.commit.assert_called_once()
        connection.close.assert_called_once()

    @patch("pipeline.tasks.translate.get_db_connection")
    @patch("pipeline.tasks.translate._fetch_article")
    def test_translate_article_not_found(self, mock_fetch_article, mock_connection_factory):
        mock_fetch_article.return_value = None
        connection = MagicMock()
        connection.cursor.return_value = MagicMock()
        mock_connection_factory.return_value = connection

        result = translate_article(article_id=999, target_language="zh-CN")

        self.assertEqual(result, {
            "article_id": 999,
            "target_language": "zh-CN",
            "status": "not_found",
        })
        connection.rollback.assert_called_once()
        connection.close.assert_called_once()

    @patch("pipeline.tasks.translate.get_db_connection")
    @patch("pipeline.tasks.translate._fetch_article")
    @patch("pipeline.tasks.translate._set_translation_status")
    @patch("pipeline.tasks.translate.is_llm_enabled")
    def test_translate_article_failed_updates_status(
        self,
        mock_llm_enabled,
        mock_set_status,
        mock_fetch_article,
        mock_connection_factory,
    ):
        mock_llm_enabled.return_value = False
        mock_fetch_article.return_value = (6, "Title", "Body", "en", "pending", "world", "headline")
        connection = MagicMock()
        connection.cursor.return_value = MagicMock()
        mock_connection_factory.return_value = connection

        with patch("pipeline.tasks.translate._upsert_translation", side_effect=RuntimeError("boom")):
            result = translate_article(article_id=6, target_language="zh-CN")

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error"], "boom")
        self.assertEqual(mock_set_status.call_args_list[-1].args[2], "failed")
        self.assertTrue(connection.rollback.called)
        self.assertTrue(connection.commit.called)
        connection.close.assert_called_once()

    @patch("pipeline.tasks.embed.get_db_connection")
    @patch("pipeline.tasks.embed._fetch_embedding_source")
    @patch("pipeline.tasks.embed._upsert_chunks")
    @patch("pipeline.tasks.embed._set_embedding_status")
    @patch("pipeline.tasks.embed.is_embedding_enabled")
    def test_embed_article_chunk_only_completed(
        self,
        mock_embedding_enabled,
        mock_set_status,
        mock_upsert_chunks,
        mock_fetch_source,
        mock_connection_factory,
    ):
        mock_embedding_enabled.return_value = False
        mock_fetch_source.return_value = (8, "Title", "Original body", "中文标题", "中文摘要", "中文正文")
        mock_upsert_chunks.return_value = [(11, 0)]
        connection = MagicMock()
        connection.cursor.return_value = MagicMock()
        mock_connection_factory.return_value = connection

        result = embed_article(article_id=8)

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["mode"], "chunk_only")
        self.assertEqual(result["chunk_count"], 1)
        self.assertEqual(mock_set_status.call_args_list[0].args[2], "processing")
        self.assertEqual(mock_set_status.call_args_list[-1].args[2], "completed")
        connection.commit.assert_called_once()
        connection.close.assert_called_once()

    @patch("pipeline.tasks.embed.get_db_connection")
    @patch("pipeline.tasks.embed._fetch_embedding_source")
    def test_embed_article_not_found(self, mock_fetch_source, mock_connection_factory):
        mock_fetch_source.return_value = None
        connection = MagicMock()
        connection.cursor.return_value = MagicMock()
        mock_connection_factory.return_value = connection

        result = embed_article(article_id=1001)

        self.assertEqual(result, {
            "article_id": 1001,
            "status": "not_found",
        })
        connection.rollback.assert_called_once()
        connection.close.assert_called_once()

    @patch("pipeline.tasks.embed.get_db_connection")
    @patch("pipeline.tasks.embed._fetch_embedding_source")
    @patch("pipeline.tasks.embed._set_embedding_status")
    def test_embed_article_failed_updates_status(
        self,
        mock_set_status,
        mock_fetch_source,
        mock_connection_factory,
    ):
        mock_fetch_source.return_value = (9, "Title", "Original body", None, None, "Translated body")
        connection = MagicMock()
        connection.cursor.return_value = MagicMock()
        mock_connection_factory.return_value = connection

        with patch("pipeline.tasks.embed._upsert_chunks", side_effect=RuntimeError("embed boom")):
            result = embed_article(article_id=9)

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error"], "embed boom")
        self.assertEqual(mock_set_status.call_args_list[-1].args[2], "failed")
        self.assertTrue(connection.rollback.called)
        self.assertTrue(connection.commit.called)
        connection.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
