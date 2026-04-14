import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from api.main import (
    _base_article_select,
    _build_filter_conditions,
    _build_keyword_condition,
    _build_keyword_score_expr,
    _cosine_similarity,
    _hybrid_rank_items,
    _normalize_empty,
    _normalize_vector,
    _paginate_items,
    _semantic_search_candidates,
    _similar_articles,
    _time_range_to_since,
    get_article,
    list_articles,
)


class ApiHelpersTest(unittest.TestCase):
    def test_normalize_empty(self):
        self.assertIsNone(_normalize_empty(None))
        self.assertIsNone(_normalize_empty("   "))
        self.assertEqual(_normalize_empty(" 德国 "), "德国")

    def test_build_filter_conditions(self):
        conditions, params = _build_filter_conditions(
            category="法规",
            country="德国",
            country_code="DEU",
            organization="欧盟",
            company="OpenAI",
            province="北京",
            city="北京",
            time_range="7d",
            alias="x",
        )

        self.assertIn("x.category LIKE %s", conditions[0])
        self.assertIn("x.country_code = %s", conditions[1])
        self.assertIn("x.country = %s", conditions[2])
        self.assertIn("x.country_code = ANY(%s)", conditions[3])
        self.assertTrue(any("x.company ILIKE %s" in condition for condition in conditions))
        self.assertTrue(any("x.province = %s" in condition for condition in conditions))
        self.assertTrue(any("x.city = %s" in condition for condition in conditions))
        self.assertTrue(any("x.publish_time >= %s" in condition for condition in conditions))
        self.assertEqual(params[0:3], ["%法规%", "DEU", "德国"])
        self.assertIn("%OpenAI%", params)
        self.assertIn("北京", params)
        self.assertEqual(len(params), 9)

    def test_build_keyword_condition(self):
        condition, params = _build_keyword_condition("欧盟", alias="a")
        self.assertIn("a.title_original ILIKE %s", condition)
        self.assertEqual(params, ["%欧盟%"] * 10)

    def test_build_keyword_condition_empty(self):
        condition, params = _build_keyword_condition(None)
        self.assertIsNone(condition)
        self.assertEqual(params, [])

    def test_normalize_vector(self):
        self.assertEqual(_normalize_vector(None), [])
        self.assertEqual(_normalize_vector([1, "2", 3.5]), [1.0, 2.0, 3.5])
        self.assertEqual(_normalize_vector((1, 2)), [1.0, 2.0])

    def test_cosine_similarity(self):
        self.assertAlmostEqual(_cosine_similarity([1, 0], [1, 0]), 1.0)
        self.assertAlmostEqual(_cosine_similarity([1, 0], [0, 1]), 0.0)
        self.assertEqual(_cosine_similarity([], [1, 0]), 0.0)
        self.assertEqual(_cosine_similarity([1, 2], [1]), 0.0)

    def test_paginate_items(self):
        payload = _paginate_items(
            [{"id": 1}, {"id": 2}, {"id": 3}, {"id": 4}, {"id": 5}],
            page=2,
            page_size=2,
        )
        self.assertEqual(payload["items"], [{"id": 3}, {"id": 4}])
        self.assertEqual(
            payload["pagination"],
            {
                "page": 2,
                "page_size": 2,
                "total": 5,
                "total_pages": 3,
            },
        )

    def test_paginate_items_empty(self):
        payload = _paginate_items([], page=1, page_size=10)
        self.assertEqual(payload["items"], [])
        self.assertEqual(payload["pagination"]["total_pages"], 0)

    def test_keyword_score_expr_and_base_select(self):
        score_expr = _build_keyword_score_expr("x")
        self.assertIn("x.title_original ILIKE %s", score_expr)
        self.assertIn("COALESCE(t.summary_translated, '') ILIKE %s", score_expr)

        base_select = _base_article_select("42 AS extra_score")
        self.assertIn("42 AS extra_score", base_select)
        self.assertIn("FROM articles a", base_select)
        self.assertIn("LEFT JOIN article_translations t", base_select)

    @patch("api.main.datetime")
    def test_time_range_to_since(self, mock_datetime):
        fixed_now = datetime(2026, 4, 9, 12, 0, 0)
        mock_datetime.now.return_value = fixed_now
        mock_datetime.min = datetime.min

        self.assertIsNone(_time_range_to_since(None))
        self.assertIsNone(_time_range_to_since("all"))
        self.assertEqual(_time_range_to_since("1d"), fixed_now - timedelta(days=1))
        self.assertEqual(_time_range_to_since("6m"), fixed_now - timedelta(days=180))
        self.assertIsNone(_time_range_to_since("invalid"))

    @patch("api.main._semantic_search_candidates")
    @patch("api.main._keyword_search_candidates")
    def test_list_articles_falls_back_to_keyword_when_query_is_empty(self, mock_keyword, mock_semantic):
        mock_keyword.return_value = [{"id": 1, "title": "A"}]

        result = list_articles(
            q="   ",
            category="法规",
            country="德国",
            country_code="DEU",
            organization="欧盟",
            company=None,
            province=None,
            city=None,
            time_range="7d",
            search_mode="semantic",
            page=1,
            page_size=10,
        )

        self.assertEqual(result["search"], {"mode": "keyword", "query": None})
        self.assertEqual(result["items"], [{"id": 1, "title": "A"}])
        mock_keyword.assert_called_once_with(
            search_term=None,
            category="法规",
            country="德国",
            country_code="DEU",
            organization="欧盟",
            company=None,
            province=None,
            city=None,
            time_range="7d",
        )
        mock_semantic.assert_not_called()

    @patch("api.main._semantic_search_candidates")
    def test_list_articles_semantic_branch(self, mock_semantic):
        mock_semantic.return_value = [
            {"id": 2, "title": "B", "semantic_score": 0.91},
            {"id": 1, "title": "A", "semantic_score": 0.72},
        ]

        result = list_articles(
            q="欧盟 AI",
            search_mode="semantic",
            time_range="all",
            semantic_limit=123,
            page=1,
            page_size=1,
        )

        self.assertEqual(result["search"], {"mode": "semantic", "query": "欧盟 AI"})
        self.assertEqual(result["items"], [{"id": 2, "title": "B", "semantic_score": 0.91}])
        self.assertEqual(result["pagination"]["total"], 2)
        mock_semantic.assert_called_once_with(
            search_term="欧盟 AI",
            category=None,
            country=None,
            country_code=None,
            organization=None,
            company=None,
            province=None,
            city=None,
            time_range="all",
            semantic_limit=123,
        )

    @patch("api.main.is_embedding_enabled", return_value=False)
    def test_semantic_search_candidates_raise_400_when_embedding_disabled(self, mock_embedding_enabled):
        with self.assertRaises(HTTPException) as context:
            _semantic_search_candidates(
                search_term="欧盟 AI",
                category=None,
                country=None,
                country_code=None,
                organization=None,
                company=None,
                province=None,
                city=None,
                time_range="all",
                semantic_limit=50,
            )

        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(
            context.exception.detail,
            "Semantic search is unavailable: embedding provider is not configured",
        )
        mock_embedding_enabled.assert_called_once_with()

    @patch("api.main._semantic_search_candidates")
    def test_list_articles_semantic_branch_propagates_semantic_400(self, mock_semantic):
        mock_semantic.side_effect = HTTPException(
            status_code=400,
            detail="Semantic search is unavailable: embedding provider is not configured",
        )

        with self.assertRaises(HTTPException) as context:
            list_articles(
                q="欧盟 AI",
                search_mode="semantic",
                time_range="all",
                semantic_limit=123,
                page=1,
                page_size=10,
            )

        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(
            context.exception.detail,
            "Semantic search is unavailable: embedding provider is not configured",
        )

    @patch("api.main._semantic_search_candidates")
    @patch("api.main._keyword_search_candidates")
    def test_list_articles_hybrid_ranking_merges_keyword_and_semantic_scores(self, mock_keyword, mock_semantic):
        newer = datetime(2026, 4, 9, 12, 0, 0)
        older = datetime(2026, 4, 8, 12, 0, 0)

        mock_keyword.return_value = [
            {"id": 1, "title": "Keyword Heavy", "keyword_score": 1, "publish_time": older},
            {"id": 2, "title": "Balanced", "keyword_score": 1, "publish_time": newer},
        ]
        mock_semantic.return_value = [
            {"id": 2, "title": "Balanced", "semantic_score": 0.9, "publish_time": newer},
            {"id": 3, "title": "Semantic Only", "semantic_score": 0.8, "publish_time": older},
        ]

        result = list_articles(
            q="OpenAI 欧盟合规",
            search_mode="hybrid",
            page=1,
            page_size=10,
        )

        self.assertEqual(
            result["search"],
            {
                "mode": "hybrid",
                "query": "OpenAI 欧盟合规",
                "weights": {"keyword": 0.35, "semantic": 0.65},
            },
        )
        self.assertEqual([item["id"] for item in result["items"]], [2, 3, 1])
        self.assertEqual(result["items"][0]["semantic_score"], 0.9)
        self.assertEqual(result["items"][0]["keyword_score"], 1)
        self.assertEqual(result["items"][1]["keyword_score"], 0)
        self.assertEqual(result["items"][1]["semantic_score"], 0.8)

    @patch("api.main.get_hybrid_ranking_weights")
    def test_hybrid_rank_items_uses_runtime_weights(self, mock_weights):
        newer = datetime(2026, 4, 9, 12, 0, 0)
        older = datetime(2026, 4, 8, 12, 0, 0)
        mock_weights.return_value = {"keyword": 0.8, "semantic": 0.2}

        ranked = _hybrid_rank_items(
            keyword_items=[
                {"id": 1, "title": "Keyword Heavy", "keyword_score": 2, "publish_time": older},
                {"id": 2, "title": "Balanced", "keyword_score": 1, "publish_time": newer},
            ],
            semantic_items=[
                {"id": 2, "title": "Balanced", "semantic_score": 0.95, "publish_time": newer},
                {"id": 3, "title": "Semantic Only", "semantic_score": 1.0, "publish_time": newer},
            ],
        )

        self.assertEqual([item["id"] for item in ranked], [1, 2, 3])

    @patch("api.main._semantic_search_candidates")
    @patch("api.main._keyword_search_candidates")
    def test_list_articles_hybrid_uses_publish_time_to_break_score_ties(self, mock_keyword, mock_semantic):
        newer = datetime(2026, 4, 9, 12, 0, 0)
        older = datetime(2026, 4, 8, 12, 0, 0)

        mock_keyword.return_value = [
            {"id": 1, "title": "Older item", "keyword_score": 1, "publish_time": older},
            {"id": 2, "title": "Newer item", "keyword_score": 1, "publish_time": newer},
        ]
        mock_semantic.return_value = [
            {"id": 1, "title": "Older item", "semantic_score": 1.0, "publish_time": older},
            {"id": 2, "title": "Newer item", "semantic_score": 1.0, "publish_time": newer},
        ]

        result = list_articles(
            q="tie-break query",
            search_mode="hybrid",
            page=1,
            page_size=10,
        )

        self.assertEqual([item["id"] for item in result["items"]], [2, 1])

    @patch("api.main._semantic_search_candidates")
    @patch("api.main._keyword_search_candidates")
    def test_list_articles_hybrid_propagates_semantic_400(self, mock_keyword, mock_semantic):
        mock_keyword.return_value = [{"id": 1, "title": "Keyword only", "keyword_score": 2}]
        mock_semantic.side_effect = HTTPException(
            status_code=400,
            detail="Semantic search is unavailable: embedding provider is not configured",
        )

        with self.assertRaises(HTTPException) as context:
            list_articles(
                q="欧盟 AI",
                search_mode="hybrid",
                page=1,
                page_size=10,
            )

        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(
            context.exception.detail,
            "Semantic search is unavailable: embedding provider is not configured",
        )

    @patch("api.main._similar_articles")
    @patch("api.main.get_db_connection")
    def test_get_article_returns_article_chunks_and_similar_items(self, mock_connection_factory, mock_similar_articles):
        article = {
            "id": 7,
            "title_original": "Original title",
            "title_translated": "中文标题",
            "source_url": "https://example.com/article",
        }
        chunks = [
            {"chunk_index": 0, "content_text": "chunk-1", "token_count": 10, "embedding_status": "completed"},
            {"chunk_index": 1, "content_text": "chunk-2", "token_count": 12, "embedding_status": "completed"},
        ]
        similar = [{"id": 9, "title": "Related article", "similarity_score": 0.88}]

        cursor = MagicMock()
        cursor.fetchone.side_effect = [article]
        cursor.fetchall.side_effect = [chunks]
        connection = MagicMock()
        connection.cursor.return_value = cursor
        mock_connection_factory.return_value = connection
        mock_similar_articles.return_value = similar

        result = get_article(7)

        self.assertEqual(result["article"], article)
        self.assertEqual(result["chunks"], chunks)
        self.assertEqual(result["similar_articles"], similar)
        self.assertEqual(cursor.execute.call_count, 2)
        mock_similar_articles.assert_called_once_with(7)
        connection.close.assert_called_once()

    @patch("api.main.get_db_connection")
    def test_get_article_raises_404_when_article_missing(self, mock_connection_factory):
        cursor = MagicMock()
        cursor.fetchone.return_value = None
        connection = MagicMock()
        connection.cursor.return_value = cursor
        mock_connection_factory.return_value = connection

        with self.assertRaises(HTTPException) as context:
            get_article(404)

        self.assertEqual(context.exception.status_code, 404)
        self.assertEqual(context.exception.detail, "Article not found")
        connection.close.assert_called_once()

    @patch("api.main.get_db_connection")
    @patch("api.main.embed_texts")
    @patch("api.main.is_embedding_enabled", return_value=True)
    def test_semantic_search_candidates_keep_highest_score_per_article(
        self,
        mock_embedding_enabled,
        mock_embed_texts,
        mock_connection_factory,
    ):
        mock_embed_texts.return_value = ([[1.0, 0.0]], "demo-model")
        rows = [
            {
                "id": 1,
                "title": "Article 1 low",
                "publish_time": datetime(2026, 4, 8, 12, 0, 0),
                "embedding_vector": [0.2, 0.98],
                "chunk_index": 0,
            },
            {
                "id": 1,
                "title": "Article 1 high",
                "publish_time": datetime(2026, 4, 8, 12, 0, 0),
                "embedding_vector": [1.0, 0.0],
                "chunk_index": 1,
            },
            {
                "id": 2,
                "title": "Article 2",
                "publish_time": datetime(2026, 4, 9, 12, 0, 0),
                "embedding_vector": [0.8, 0.2],
                "chunk_index": 0,
            },
        ]
        cursor = MagicMock()
        cursor.fetchall.return_value = rows
        connection = MagicMock()
        connection.cursor.return_value = cursor
        mock_connection_factory.return_value = connection

        result = _semantic_search_candidates(
            search_term="欧盟 AI",
            category=None,
            country=None,
            country_code=None,
            organization=None,
            company=None,
            province=None,
            city=None,
            time_range="all",
            semantic_limit=20,
        )

        self.assertEqual([item["id"] for item in result], [1, 2])
        self.assertEqual(result[0]["title"], "Article 1 high")
        self.assertAlmostEqual(result[0]["semantic_score"], 1.0)
        self.assertEqual(len(result), 2)
        mock_embedding_enabled.assert_called_once_with()
        mock_embed_texts.assert_called_once_with(["欧盟 AI"])
        connection.close.assert_called_once()

    @patch("api.main._get_article_embedding_vectors")
    def test_similar_articles_returns_empty_when_no_embeddings(self, mock_get_article_vectors):
        mock_get_article_vectors.return_value = (None, [])

        result = _similar_articles(7)

        self.assertEqual(result, [])
        mock_get_article_vectors.assert_called_once_with(7)

    @patch("api.main.get_db_connection")
    @patch("api.main._get_article_embedding_vectors")
    def test_similar_articles_use_best_chunk_similarity_per_article(
        self,
        mock_get_article_vectors,
        mock_connection_factory,
    ):
        mock_get_article_vectors.return_value = ("demo-model", [[1.0, 0.0], [0.0, 1.0]])
        rows = [
            {
                "id": 11,
                "title": "Article 11 low",
                "publish_time": datetime(2026, 4, 8, 12, 0, 0),
                "embedding_vector": [0.1, 0.9],
                "embedding_model": "demo-model",
                "chunk_index": 0,
            },
            {
                "id": 11,
                "title": "Article 11 high",
                "publish_time": datetime(2026, 4, 8, 12, 0, 0),
                "embedding_vector": [1.0, 0.0],
                "embedding_model": "demo-model",
                "chunk_index": 1,
            },
            {
                "id": 12,
                "title": "Article 12",
                "publish_time": datetime(2026, 4, 9, 12, 0, 0),
                "embedding_vector": [0.8, 0.2],
                "embedding_model": "demo-model",
                "chunk_index": 0,
            },
        ]
        cursor = MagicMock()
        cursor.fetchall.return_value = rows
        connection = MagicMock()
        connection.cursor.return_value = cursor
        mock_connection_factory.return_value = connection

        result = _similar_articles(7, limit=5, candidate_limit=20)

        self.assertEqual([item["id"] for item in result], [11, 12])
        self.assertEqual(result[0]["title"], "Article 11 high")
        self.assertAlmostEqual(result[0]["similarity_score"], 1.0)
        self.assertEqual(len(result), 2)
        connection.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
