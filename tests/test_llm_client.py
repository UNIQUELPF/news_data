import os
import unittest
from unittest.mock import patch
from unittest.mock import MagicMock

from pipeline.llm_client import (
    LLMClientError,
    _extract_json_payload,
    _strip_trailing_slash,
    extract_domestic_article_metadata,
    get_embedding_model,
    get_embedding_provider,
    get_llm_base_url,
    get_pipeline_runtime_status,
    get_translation_mode,
    is_embedding_enabled,
)


class LlmClientHelpersTest(unittest.TestCase):
    def test_strip_trailing_slash(self):
        self.assertEqual(_strip_trailing_slash("https://example.com/"), "https://example.com")
        self.assertEqual(_strip_trailing_slash("https://example.com"), "https://example.com")

    def test_extract_json_payload_plain_json(self):
        payload = _extract_json_payload('{"title_translated":"标题"}')
        self.assertEqual(payload["title_translated"], "标题")

    def test_extract_json_payload_markdown_wrapped(self):
        payload = _extract_json_payload("```json\n{\"summary_translated\":\"摘要\"}\n```")
        self.assertEqual(payload["summary_translated"], "摘要")

    def test_extract_json_payload_invalid(self):
        with self.assertRaises(LLMClientError):
            _extract_json_payload("no json here")

    @patch("pipeline.llm_client.httpx.Client")
    @patch.dict(
        os.environ,
        {
            "OPENAI_API_KEY": "test-key",
            "OPENAI_BASE_URL": "https://api.example.com/v1/",
            "TRANSLATION_MODEL": "gpt-4.1-mini",
        },
        clear=True,
    )
    def test_extract_domestic_article_metadata(self, mock_client_cls):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": '{"category":"经济","province":"北京","city":"北京","involved_companies":"中国汽车工业协会","confidence":0.93}'
                    }
                }
            ]
        }
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value.__enter__.return_value = mock_client

        payload = extract_domestic_article_metadata(title="3月我国汽车产销环比大幅回升", content="中国汽车工业协会数据显示...")

        self.assertEqual(payload["category"], "经济")
        self.assertEqual(payload["province"], "北京")
        self.assertEqual(payload["city"], "北京")
        self.assertEqual(payload["involved_companies"], "中国汽车工业协会")
        self.assertEqual(payload["confidence"], 0.93)

    @patch.dict(os.environ, {}, clear=True)
    def test_default_embedding_provider_and_model(self):
        self.assertEqual(get_embedding_provider(), "openai")
        self.assertEqual(get_embedding_model(), "text-embedding-3-small")
        self.assertFalse(is_embedding_enabled())

    @patch.dict(
        os.environ,
        {
            "EMBEDDING_PROVIDER": "demo",
            "DEMO_EMBEDDING_MODEL": "demo-semantic-v1",
        },
        clear=True,
    )
    def test_demo_embedding_provider(self):
        self.assertEqual(get_embedding_provider(), "demo")
        self.assertEqual(get_embedding_model(), "demo-semantic-v1")
        self.assertTrue(is_embedding_enabled())

    @patch.dict(os.environ, {}, clear=True)
    def test_pipeline_runtime_status_reports_placeholder_and_missing_embedding(self):
        status = get_pipeline_runtime_status()

        self.assertEqual(get_translation_mode(), "placeholder")
        self.assertFalse(status["production_ready"])
        self.assertIn("Translation is running in placeholder mode", status["warnings"])
        self.assertIn("small", status["recommended_rollout"])
        self.assertEqual(status["search"]["hybrid_weights"], {"keyword": 0.35, "semantic": 0.65})

    @patch.dict(
        os.environ,
        {
            "OPENAI_API_KEY": "test-key",
            "OPENAI_BASE_URL": "https://api.example.com/v1/",
            "TRANSLATION_MODEL": "gpt-4.1-mini",
            "EMBEDDING_PROVIDER": "openai",
            "EMBEDDING_MODEL": "text-embedding-3-small",
        },
        clear=True,
    )
    def test_llm_base_url_and_openai_embedding_enabled(self):
        self.assertEqual(get_llm_base_url(), "https://api.example.com/v1")
        self.assertTrue(is_embedding_enabled())

    @patch.dict(
        os.environ,
        {
            "OPENAI_API_KEY": "test-key",
            "OPENAI_BASE_URL": "https://api.example.com/v1/",
            "TRANSLATION_MODEL": "gpt-4.1-mini",
            "EMBEDDING_PROVIDER": "openai",
            "EMBEDDING_MODEL": "text-embedding-3-small",
        },
        clear=True,
    )
    def test_pipeline_runtime_status_reports_production_ready_for_openai(self):
        status = get_pipeline_runtime_status()

        self.assertTrue(status["production_ready"])
        self.assertEqual(status["translation"]["mode"], "llm")
        self.assertEqual(status["embedding"]["provider"], "openai")
        self.assertEqual(status["warnings"], [])


if __name__ == "__main__":
    unittest.main()
