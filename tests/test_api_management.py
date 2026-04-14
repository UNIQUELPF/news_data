import unittest
from unittest.mock import MagicMock, patch

from fastapi import HTTPException
from starlette.requests import Request

from api.main import (
    BackfillRequest,
    PipelineRunRequest,
    cancel_pipeline_task,
    get_task_status,
    list_pipeline_presets,
    list_pipeline_tasks,
    pipeline_runtime,
    pipeline_summary,
    retry_pipeline_task,
    trigger_backfill,
    trigger_pipeline_run,
)


def _build_request(*, client_host="127.0.0.1"):
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/",
        "headers": [],
        "client": (client_host, 12345),
        "scheme": "http",
        "server": ("testserver", 80),
        "query_string": b"",
    }
    return Request(scope)


class ApiManagementTest(unittest.TestCase):
    @patch("api.main._record_pipeline_task")
    @patch("api.main.run_translation_embedding_backfill")
    @patch("api.main.ADMIN_API_TOKEN", "secret-token")
    def test_trigger_backfill(self, mock_backfill_task, mock_record_task):
        mock_backfill_task.delay.return_value = MagicMock(id="task-123")

        response = trigger_backfill(
            request=BackfillRequest(
                target_language="zh-CN",
                translate_limit=5,
                embed_limit=6,
                force_translate=True,
                force_embed=False,
            ),
            http_request=_build_request(),
            x_admin_token="secret-token",
            x_admin_actor="tester",
            user_agent="unit-test",
            x_forwarded_for="10.0.0.8",
        )

        self.assertEqual(
            response,
            {
                "task_id": "task-123",
                "status": "queued",
                "task_name": "pipeline.tasks.backfill.run_translation_embedding_backfill",
                "params": {
                    "target_language": "zh-CN",
                    "translate_limit": 5,
                    "embed_limit": 6,
                    "force_translate": True,
                    "force_embed": False,
                },
                "requested_by": "tester",
            },
        )
        mock_backfill_task.delay.assert_called_once_with(
            target_language="zh-CN",
            translate_limit=5,
            embed_limit=6,
            force_translate=True,
            force_embed=False,
        )
        mock_record_task.assert_called_once()

    @patch("api.main.ADMIN_API_TOKEN", "secret-token")
    def test_trigger_backfill_rejects_invalid_token(self):
        with self.assertRaises(HTTPException) as context:
            trigger_backfill(
                request=BackfillRequest(),
                http_request=_build_request(),
                x_admin_token="wrong-token",
            )

        self.assertEqual(context.exception.status_code, 401)
        self.assertEqual(context.exception.detail, "Invalid admin token")

    @patch("api.main._record_pipeline_task")
    @patch("api.main.run_end_to_end_pipeline")
    @patch("api.main.ADMIN_API_TOKEN", "secret-token")
    def test_trigger_pipeline_run(self, mock_pipeline_task, mock_record_task):
        mock_pipeline_task.delay.return_value = MagicMock(id="pipeline-123")

        response = trigger_pipeline_run(
            request=PipelineRunRequest(
                spiders=["malaysia_enanyang", "usa_arstechnica"],
                target_language="zh-CN",
                crawl_extra_args={"start_date": "2026-04-01"},
                translate_limit=10,
                embed_limit=12,
                force_translate=True,
                force_embed=False,
            ),
            http_request=_build_request(),
            x_admin_token="secret-token",
            x_admin_actor="tester",
            user_agent="unit-test",
            x_forwarded_for="10.0.0.8",
        )

        self.assertEqual(response["task_id"], "pipeline-123")
        self.assertEqual(response["status"], "queued")
        self.assertEqual(response["task_name"], "pipeline.tasks.orchestrate.run_end_to_end_pipeline")
        self.assertEqual(response["requested_by"], "tester")
        mock_pipeline_task.delay.assert_called_once_with(
            spiders=["malaysia_enanyang", "usa_arstechnica"],
            target_language="zh-CN",
            crawl_extra_args={"start_date": "2026-04-01"},
            translate_limit=10,
            embed_limit=12,
            force_translate=True,
            force_embed=False,
        )
        mock_record_task.assert_called_once()

    @patch("api.main._get_pipeline_task")
    @patch("api.main.celery_app.AsyncResult")
    @patch("api.main.ADMIN_API_TOKEN", "secret-token")
    def test_get_task_status(self, mock_async_result_cls, mock_get_task):
        mock_get_task.return_value = {
            "task_id": "task-1",
            "task_name": "pipeline.tasks.backfill.run_translation_embedding_backfill",
            "task_type": "backfill",
            "state": "SUCCESS",
            "params": {"target_language": "zh-CN"},
            "result": {"status": "completed"},
            "error_message": None,
            "requested_by": "tester",
            "request_ip": "127.0.0.1",
            "user_agent": "unit-test",
            "created_at": "2026-04-09T10:00:00",
            "updated_at": "2026-04-09T10:00:02",
        }

        async_result = MagicMock()
        async_result.successful.return_value = True
        async_result.failed.return_value = False
        async_result.state = "SUCCESS"
        async_result.result = {"status": "completed"}
        mock_async_result_cls.return_value = async_result

        response = get_task_status("task-1", x_admin_token="secret-token")

        self.assertEqual(response["task_id"], "task-1")
        self.assertEqual(response["state"], "SUCCESS")
        self.assertEqual(response["result"], {"status": "completed"})
        self.assertEqual(response["actions"], {"can_cancel": False, "can_retry": False})

    @patch("api.main._get_pipeline_task")
    @patch("api.main.celery_app.AsyncResult")
    @patch("api.main.ADMIN_API_TOKEN", "secret-token")
    def test_get_task_status_allows_retry_for_failed_pipeline_run(self, mock_async_result_cls, mock_get_task):
        mock_get_task.return_value = {
            "task_id": "pipeline-failed",
            "task_name": "pipeline.tasks.orchestrate.run_end_to_end_pipeline",
            "task_type": "pipeline_run",
            "state": "FAILURE",
            "params": {"spiders": ["a"]},
            "result": {"status": "partial"},
            "error_message": "boom",
            "requested_by": "tester",
            "request_ip": "127.0.0.1",
            "user_agent": "unit-test",
            "created_at": "2026-04-09T10:00:00",
            "updated_at": "2026-04-09T10:00:02",
        }

        async_result = MagicMock()
        async_result.successful.return_value = False
        async_result.failed.return_value = True
        async_result.state = "FAILURE"
        async_result.result = RuntimeError("boom")
        mock_async_result_cls.return_value = async_result

        response = get_task_status("pipeline-failed", x_admin_token="secret-token")

        self.assertEqual(response["state"], "FAILURE")
        self.assertEqual(response["task_type"], "pipeline_run")
        self.assertEqual(response["actions"], {"can_cancel": False, "can_retry": True})

    @patch("api.main._get_pipeline_task")
    @patch("api.main.celery_app.AsyncResult")
    @patch("api.main.ADMIN_API_TOKEN", "secret-token")
    def test_get_task_status_allows_retry_for_failed_backfill(self, mock_async_result_cls, mock_get_task):
        mock_get_task.return_value = {
            "task_id": "task-failed",
            "task_name": "pipeline.tasks.backfill.run_translation_embedding_backfill",
            "task_type": "backfill",
            "state": "FAILURE",
            "params": {"target_language": "zh-CN"},
            "result": {"status": "failed"},
            "error_message": "boom",
            "requested_by": "tester",
            "request_ip": "127.0.0.1",
            "user_agent": "unit-test",
            "created_at": "2026-04-09T10:00:00",
            "updated_at": "2026-04-09T10:00:02",
        }

        async_result = MagicMock()
        async_result.successful.return_value = False
        async_result.failed.return_value = True
        async_result.state = "FAILURE"
        async_result.result = RuntimeError("boom")
        mock_async_result_cls.return_value = async_result

        response = get_task_status("task-failed", x_admin_token="secret-token")

        self.assertEqual(response["state"], "FAILURE")
        self.assertEqual(response["error"], "boom")
        self.assertEqual(response["actions"], {"can_cancel": False, "can_retry": True})

    @patch("api.main._get_pipeline_task")
    @patch("api.main.celery_app.AsyncResult")
    @patch("api.main.ADMIN_API_TOKEN", "secret-token")
    def test_get_task_status_allows_retry_for_revoked_backfill(self, mock_async_result_cls, mock_get_task):
        mock_get_task.return_value = {
            "task_id": "task-revoked",
            "task_name": "pipeline.tasks.backfill.run_translation_embedding_backfill",
            "task_type": "backfill",
            "state": "REVOKED",
            "params": {"target_language": "zh-CN"},
            "result": {"cancelled": True},
            "error_message": None,
            "requested_by": "tester",
            "request_ip": "127.0.0.1",
            "user_agent": "unit-test",
            "created_at": "2026-04-09T10:00:00",
            "updated_at": "2026-04-09T10:00:02",
        }

        async_result = MagicMock()
        async_result.successful.return_value = False
        async_result.failed.return_value = False
        async_result.state = "REVOKED"
        mock_async_result_cls.return_value = async_result

        response = get_task_status("task-revoked", x_admin_token="secret-token")

        self.assertEqual(response["state"], "REVOKED")
        self.assertEqual(response["actions"], {"can_cancel": False, "can_retry": True})

    @patch("api.main._get_pipeline_task")
    @patch("api.main.ADMIN_API_TOKEN", "secret-token")
    def test_get_task_status_raises_404_when_task_missing(self, mock_get_task):
        mock_get_task.return_value = None

        with self.assertRaises(HTTPException) as context:
            get_task_status("missing-task", x_admin_token="secret-token")

        self.assertEqual(context.exception.status_code, 404)
        self.assertEqual(context.exception.detail, "Task not found")

    @patch("api.main._append_pipeline_task_note")
    @patch("api.main._sync_pipeline_task_state")
    @patch("api.main._get_pipeline_task")
    @patch("api.main.celery_app.control.revoke")
    @patch("api.main.celery_app.AsyncResult")
    @patch("api.main.ADMIN_API_TOKEN", "secret-token")
    def test_cancel_pipeline_task(
        self,
        mock_async_result_cls,
        mock_revoke,
        mock_get_task,
        mock_sync_state,
        mock_append_note,
    ):
        mock_get_task.return_value = {
            "task_id": "task-2",
            "task_name": "pipeline.tasks.backfill.run_translation_embedding_backfill",
            "task_type": "backfill",
        }
        async_result = MagicMock()
        async_result.state = "STARTED"
        mock_async_result_cls.return_value = async_result

        response = cancel_pipeline_task(
            "task-2",
            http_request=_build_request(),
            x_admin_token="secret-token",
            x_admin_actor="tester",
            user_agent="unit-test",
            x_forwarded_for="10.0.0.9",
        )

        self.assertEqual(
            response,
            {
                "task_id": "task-2",
                "state": "REVOKED",
                "status": "cancelled",
            },
        )
        mock_revoke.assert_called_once_with("task-2", terminate=True)
        mock_sync_state.assert_called_once_with("task-2", "REVOKED", {"cancelled": True, "cancelled_by": "tester"})
        mock_append_note.assert_called_once()

    @patch("api.main._get_pipeline_task")
    @patch("api.main.ADMIN_API_TOKEN", "secret-token")
    def test_cancel_pipeline_task_raises_404_when_task_missing(self, mock_get_task):
        mock_get_task.return_value = None

        with self.assertRaises(HTTPException) as context:
            cancel_pipeline_task(
                "missing-task",
                http_request=_build_request(),
                x_admin_token="secret-token",
            )

        self.assertEqual(context.exception.status_code, 404)
        self.assertEqual(context.exception.detail, "Task not found")

    @patch("api.main._append_pipeline_task_note")
    @patch("api.main._sync_pipeline_task_state")
    @patch("api.main._get_pipeline_task")
    @patch("api.main.celery_app.control.revoke")
    @patch("api.main.celery_app.AsyncResult")
    @patch("api.main.ADMIN_API_TOKEN", "secret-token")
    def test_cancel_pipeline_task_rejects_completed_task(
        self,
        mock_async_result_cls,
        mock_revoke,
        mock_get_task,
        mock_sync_state,
        mock_append_note,
    ):
        mock_get_task.return_value = {
            "task_id": "task-2",
            "task_name": "pipeline.tasks.backfill.run_translation_embedding_backfill",
            "task_type": "backfill",
        }
        async_result = MagicMock()
        async_result.state = "SUCCESS"
        mock_async_result_cls.return_value = async_result

        with self.assertRaises(HTTPException) as context:
            cancel_pipeline_task(
                "task-2",
                http_request=_build_request(),
                x_admin_token="secret-token",
            )

        self.assertEqual(context.exception.status_code, 409)
        self.assertEqual(context.exception.detail, "Task cannot be cancelled in state SUCCESS")
        mock_revoke.assert_not_called()
        mock_sync_state.assert_not_called()
        mock_append_note.assert_not_called()

    @patch("api.main._append_pipeline_task_note")
    @patch("api.main._record_pipeline_task")
    @patch("api.main._get_pipeline_task")
    @patch("api.main.run_translation_embedding_backfill")
    @patch("api.main.celery_app.AsyncResult")
    @patch("api.main.ADMIN_API_TOKEN", "secret-token")
    def test_retry_pipeline_task(
        self,
        mock_async_result_cls,
        mock_backfill_task,
        mock_get_task,
        mock_record_task,
        mock_append_note,
    ):
        mock_get_task.return_value = {
            "task_id": "task-old",
            "task_name": "pipeline.tasks.backfill.run_translation_embedding_backfill",
            "task_type": "backfill",
            "params": {
                "target_language": "zh-CN",
                "translate_limit": 7,
                "embed_limit": 8,
                "force_translate": True,
                "force_embed": False,
            },
        }
        async_result = MagicMock()
        async_result.state = "FAILURE"
        mock_async_result_cls.return_value = async_result
        mock_backfill_task.delay.return_value = MagicMock(id="task-new")

        response = retry_pipeline_task(
            "task-old",
            http_request=_build_request(),
            x_admin_token="secret-token",
            x_admin_actor="tester",
            user_agent="unit-test",
            x_forwarded_for="10.0.0.10",
        )

        self.assertEqual(
            response,
            {
                "task_id": "task-new",
                "status": "queued",
                "retried_from": "task-old",
                "params": {
                    "target_language": "zh-CN",
                    "translate_limit": 7,
                    "embed_limit": 8,
                    "force_translate": True,
                    "force_embed": False,
                },
            },
        )
        mock_backfill_task.delay.assert_called_once_with(
            target_language="zh-CN",
            translate_limit=7,
            embed_limit=8,
            force_translate=True,
            force_embed=False,
        )
        mock_record_task.assert_called_once()
        mock_append_note.assert_called_once()

    @patch("api.main._append_pipeline_task_note")
    @patch("api.main._record_pipeline_task")
    @patch("api.main._get_pipeline_task")
    @patch("api.main.run_end_to_end_pipeline")
    @patch("api.main.celery_app.AsyncResult")
    @patch("api.main.ADMIN_API_TOKEN", "secret-token")
    def test_retry_pipeline_run_task(
        self,
        mock_async_result_cls,
        mock_pipeline_task,
        mock_get_task,
        mock_record_task,
        mock_append_note,
    ):
        mock_get_task.return_value = {
            "task_id": "pipeline-old",
            "task_name": "pipeline.tasks.orchestrate.run_end_to_end_pipeline",
            "task_type": "pipeline_run",
            "params": {
                "spiders": ["malaysia_enanyang", "usa_arstechnica"],
                "target_language": "zh-CN",
                "crawl_extra_args": {"start_date": "2026-04-01"},
                "translate_limit": 15,
                "embed_limit": 18,
                "force_translate": True,
                "force_embed": False,
            },
        }
        async_result = MagicMock()
        async_result.state = "FAILURE"
        mock_async_result_cls.return_value = async_result
        mock_pipeline_task.delay.return_value = MagicMock(id="pipeline-new")

        response = retry_pipeline_task(
            "pipeline-old",
            http_request=_build_request(),
            x_admin_token="secret-token",
            x_admin_actor="tester",
            user_agent="unit-test",
            x_forwarded_for="10.0.0.11",
        )

        self.assertEqual(
            response,
            {
                "task_id": "pipeline-new",
                "status": "queued",
                "retried_from": "pipeline-old",
                "params": {
                    "spiders": ["malaysia_enanyang", "usa_arstechnica"],
                    "target_language": "zh-CN",
                    "crawl_extra_args": {"start_date": "2026-04-01"},
                    "translate_limit": 15,
                    "embed_limit": 18,
                    "force_translate": True,
                    "force_embed": False,
                },
            },
        )
        mock_pipeline_task.delay.assert_called_once_with(
            spiders=["malaysia_enanyang", "usa_arstechnica"],
            target_language="zh-CN",
            crawl_extra_args={"start_date": "2026-04-01"},
            translate_limit=15,
            embed_limit=18,
            force_translate=True,
            force_embed=False,
        )
        mock_record_task.assert_called_once()
        mock_append_note.assert_called_once()

    @patch("api.main._get_pipeline_task")
    @patch("api.main.ADMIN_API_TOKEN", "secret-token")
    def test_retry_pipeline_task_raises_404_when_task_missing(self, mock_get_task):
        mock_get_task.return_value = None

        with self.assertRaises(HTTPException) as context:
            retry_pipeline_task(
                "missing-task",
                http_request=_build_request(),
                x_admin_token="secret-token",
            )

        self.assertEqual(context.exception.status_code, 404)
        self.assertEqual(context.exception.detail, "Task not found")

    @patch("api.main._get_pipeline_task")
    @patch("api.main.ADMIN_API_TOKEN", "secret-token")
    def test_retry_pipeline_task_rejects_non_retryable_task(self, mock_get_task):
        mock_get_task.return_value = {
            "task_id": "task-old",
            "task_name": "pipeline.tasks.translate.translate_backfill_articles",
            "task_type": "translate",
            "params": {},
        }

        with self.assertRaises(HTTPException) as context:
            retry_pipeline_task(
                "task-old",
                http_request=_build_request(),
                x_admin_token="secret-token",
            )

        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(context.exception.detail, "Only backfill and pipeline_run tasks can be retried")

    @patch("api.main._record_pipeline_task")
    @patch("api.main._append_pipeline_task_note")
    @patch("api.main._get_pipeline_task")
    @patch("api.main.run_translation_embedding_backfill")
    @patch("api.main.celery_app.AsyncResult")
    @patch("api.main.ADMIN_API_TOKEN", "secret-token")
    def test_retry_pipeline_task_rejects_active_task(
        self,
        mock_async_result_cls,
        mock_backfill_task,
        mock_get_task,
        mock_append_note,
        mock_record_task,
    ):
        mock_get_task.return_value = {
            "task_id": "task-old",
            "task_name": "pipeline.tasks.backfill.run_translation_embedding_backfill",
            "task_type": "backfill",
            "params": {"target_language": "zh-CN"},
        }
        async_result = MagicMock()
        async_result.state = "STARTED"
        mock_async_result_cls.return_value = async_result

        with self.assertRaises(HTTPException) as context:
            retry_pipeline_task(
                "task-old",
                http_request=_build_request(),
                x_admin_token="secret-token",
            )

        self.assertEqual(context.exception.status_code, 409)
        self.assertEqual(context.exception.detail, "Task is still active in state STARTED")
        mock_backfill_task.delay.assert_not_called()
        mock_append_note.assert_not_called()
        mock_record_task.assert_not_called()

    @patch("api.main._list_recent_pipeline_tasks")
    @patch("api.main.ADMIN_API_TOKEN", "secret-token")
    def test_list_pipeline_tasks(self, mock_list_tasks):
        mock_list_tasks.return_value = [
            {"task_id": "task-1", "state": "SUCCESS"},
            {"task_id": "task-2", "state": "PENDING"},
        ]

        response = list_pipeline_tasks(task_type="backfill", limit=5, x_admin_token="secret-token")

        self.assertEqual(
            response,
            {
                "items": [
                    {"task_id": "task-1", "state": "SUCCESS"},
                    {"task_id": "task-2", "state": "PENDING"},
                ]
            },
        )
        mock_list_tasks.assert_called_once_with(task_type="backfill", limit=5)

    @patch("api.main.ADMIN_API_TOKEN", "secret-token")
    def test_list_pipeline_presets(self):
        response = list_pipeline_presets(x_admin_token="secret-token")

        self.assertIn("items", response)
        self.assertGreaterEqual(len(response["items"]), 3)
        self.assertEqual(response["items"][0]["id"], "malaysia_sample")

    @patch("api.main.get_pipeline_runtime_status")
    @patch("api.main.ADMIN_API_TOKEN", "secret-token")
    def test_pipeline_runtime(self, mock_runtime_status):
        mock_runtime_status.return_value = {
            "translation": {"mode": "llm"},
            "embedding": {"provider": "local"},
            "production_ready": True,
            "warnings": [],
        }

        response = pipeline_runtime(x_admin_token="secret-token")

        self.assertEqual(response["production_ready"], True)
        self.assertEqual(response["translation"]["mode"], "llm")
        mock_runtime_status.assert_called_once_with()

    @patch("api.main._pipeline_task_monitor_summary")
    @patch("api.main._crawl_monitor_summary")
    @patch("api.main.pipeline_summary")
    @patch("api.main.ADMIN_API_TOKEN", "secret-token")
    def test_pipeline_monitor(self, mock_pipeline_summary, mock_crawl_summary, mock_task_monitor):
        mock_pipeline_summary.return_value = {"total_articles": 12}
        mock_crawl_summary.return_value = {
            "crawl_jobs_24h": 5,
            "items_scraped_24h": 31,
            "latest_crawls": [],
            "failed_spiders_24h": [{"spider_name": "usa_reuters", "failed_count": 3}],
            "spider_health_24h": [{"spider_name": "malaysia_enanyang", "success_count": 4, "failed_count": 1, "total_count": 5, "success_rate": 80.0}],
            "recent_failures": [{"spider_name": "usa_reuters", "error_message": "401 unauthorized"}],
        }
        mock_task_monitor.return_value = {
            "pending_tasks": 2,
            "started_tasks": 1,
            "retry_tasks": 1,
            "backfill_active": 2,
            "pipeline_run_active": 1,
        }

        from api.main import pipeline_monitor

        response = pipeline_monitor(x_admin_token="secret-token")

        self.assertEqual(response["pipeline"], {"total_articles": 12})
        self.assertEqual(response["crawl"]["crawl_jobs_24h"], 5)
        self.assertEqual(response["tasks"]["pending_tasks"], 2)
        self.assertEqual(response["crawl"]["failed_spiders_24h"][0]["spider_name"], "usa_reuters")
        self.assertEqual(response["crawl"]["spider_health_24h"][0]["success_rate"], 80.0)
        self.assertEqual(response["crawl"]["recent_failures"][0]["error_message"], "401 unauthorized")
        mock_pipeline_summary.assert_called_once_with(x_admin_token="secret-token")
        mock_crawl_summary.assert_called_once_with()
        mock_task_monitor.assert_called_once_with()

    @patch("api.main.get_db_connection")
    @patch("api.main.ADMIN_API_TOKEN", "secret-token")
    def test_pipeline_summary_returns_counts(self, mock_connection_factory):
        expected = {
            "total_articles": 12,
            "translation_pending": 2,
            "translation_processing": 1,
            "translation_completed": 7,
            "translation_failed": 2,
            "embedding_pending": 3,
            "embedding_processing": 1,
            "embedding_completed": 6,
            "embedding_failed": 2,
        }
        cursor = MagicMock()
        cursor.fetchone.return_value = expected
        connection = MagicMock()
        connection.cursor.return_value = cursor
        mock_connection_factory.return_value = connection

        response = pipeline_summary(x_admin_token="secret-token")

        self.assertEqual(response, expected)
        cursor.execute.assert_called_once()
        connection.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
