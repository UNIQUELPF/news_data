import json

from pipeline.celery_app import celery_app
from pipeline.db import get_db_connection
from pipeline.llm_client import (
    embed_texts,
    get_embedding_model,
    get_embedding_provider,
    is_embedding_enabled,
)


def _set_embedding_status(cursor, article_id: int, status: str):
    cursor.execute(
        """
        UPDATE articles
        SET embedding_status = %s, updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (status, article_id),
    )


def _claim_next_pending_articles(cursor, limit: int = 1):
    cursor.execute(
        """
        WITH candidate AS (
            SELECT id
            FROM articles
            WHERE embedding_status = 'pending'
              AND translation_status = 'completed'
            ORDER BY publish_time DESC NULLS LAST, id DESC
            LIMIT %s
            FOR UPDATE SKIP LOCKED
        )
        UPDATE articles a
        SET embedding_status = 'processing', updated_at = CURRENT_TIMESTAMP
        FROM candidate
        WHERE a.id = candidate.id
        RETURNING a.id
        """,
        (limit,),
    )
    return [row[0] for row in cursor.fetchall()]


def _select_backfill_article_ids(cursor, limit: int, force: bool = False) -> list[int]:
    if force:
        cursor.execute(
            """
            SELECT a.id
            FROM articles a
            WHERE a.translation_status = 'completed'
            ORDER BY a.publish_time DESC NULLS LAST, a.id DESC
            LIMIT %s
            """,
            (limit,),
        )
    else:
        cursor.execute(
            """
            SELECT a.id
            FROM articles a
            WHERE a.translation_status = 'completed'
              AND (
                    a.embedding_status IN ('pending', 'failed')
                    OR NOT EXISTS (
                        SELECT 1
                        FROM article_embeddings e
                        WHERE e.article_id = a.id
                    )
                  )
            ORDER BY a.publish_time DESC NULLS LAST, a.id DESC
            LIMIT %s
            """,
            (limit,),
        )
    return [row[0] for row in cursor.fetchall()]


def _fetch_embedding_source(cursor, article_id: int, target_language: str):
    cursor.execute(
        """
        SELECT
            a.id,
            a.title_original,
            a.content_original,
            t.title_translated,
            t.summary_translated,
            t.content_translated
        FROM articles a
        LEFT JOIN article_translations t
            ON t.article_id = a.id
           AND t.target_language = %s
        WHERE a.id = %s
        """,
        (target_language, article_id),
    )
    return cursor.fetchone()


def _chunk_text(text: str | None, chunk_size: int = 1200) -> list[str]:
    if not text:
        return []
    compact = " ".join(text.split())
    return [compact[i:i + chunk_size] for i in range(0, len(compact), chunk_size)]


def _upsert_chunks(cursor, article_id: int, chunks: list[str]) -> list[tuple[int, int]]:
    cursor.execute("DELETE FROM article_embeddings WHERE article_id = %s", (article_id,))
    cursor.execute("DELETE FROM article_chunks WHERE article_id = %s", (article_id,))
    chunk_refs: list[tuple[int, int]] = []
    for index, chunk in enumerate(chunks):
        cursor.execute(
            """
            INSERT INTO article_chunks (
                article_id,
                chunk_index,
                content_text,
                token_count,
                embedding_status,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            RETURNING id, chunk_index
            """,
            (
                article_id,
                index,
                chunk,
                max(1, len(chunk) // 4),
                "completed" if is_embedding_enabled() else "pending",
            ),
        )
        chunk_refs.append(cursor.fetchone())
    return chunk_refs


def _upsert_embeddings(cursor, article_id: int, chunk_refs: list[tuple[int, int]], vectors: list[list[float]], model_name: str):
    for (chunk_id, chunk_index), vector in zip(chunk_refs, vectors):
        cursor.execute(
            """
            INSERT INTO article_embeddings (
                article_id,
                chunk_id,
                chunk_index,
                embedding_model,
                embedding_dimensions,
                embedding_vector,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s::jsonb, CURRENT_TIMESTAMP)
            ON CONFLICT (article_id, chunk_index, embedding_model) DO UPDATE SET
                chunk_id = EXCLUDED.chunk_id,
                embedding_dimensions = EXCLUDED.embedding_dimensions,
                embedding_vector = EXCLUDED.embedding_vector,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                article_id,
                chunk_id,
                chunk_index,
                model_name,
                len(vector),
                json.dumps(vector),
            ),
        )
        cursor.execute(
            """
            UPDATE article_chunks
            SET embedding_status = 'completed', updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (chunk_id,),
        )


@celery_app.task(name="pipeline.tasks.embed.embed_article")
def embed_article(article_id: int, parent_task_id: str | None = None) -> dict:
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        _set_embedding_status(cursor, article_id, "processing")
        row = _fetch_embedding_source(cursor, article_id, "zh-CN")
        if not row:
            connection.rollback()
            return {
                "article_id": article_id,
                "status": "not_found",
            }

        content_text = row[5] or row[4] or row[2] or ""
        title_text = row[3] or row[1] or ""
        chunks = _chunk_text("\n\n".join(part for part in [title_text, content_text] if part))
        chunk_refs = _upsert_chunks(cursor, article_id, chunks)
        if is_embedding_enabled() and chunks:
            vectors, model_name = embed_texts(chunks)
            _upsert_embeddings(cursor, article_id, chunk_refs, vectors, model_name)
        _set_embedding_status(cursor, article_id, "completed")
        connection.commit()
        return {
            "article_id": article_id,
            "status": "completed",
            "chunk_count": len(chunks),
            "embedding_model": get_embedding_model() if is_embedding_enabled() else None,
            "provider": get_embedding_provider() if is_embedding_enabled() else None,
            "mode": get_embedding_provider() if is_embedding_enabled() else "chunk_only",
        }
    except Exception as exc:
        connection.rollback()
        try:
            cursor = connection.cursor()
            _set_embedding_status(cursor, article_id, "failed")
            connection.commit()
        except Exception:
            connection.rollback()
        return {
            "article_id": article_id,
            "status": "failed",
            "error": str(exc),
        }
    finally:
        connection.close()


@celery_app.task(name="pipeline.tasks.embed.auto_embed_articles", bind=True)
def auto_embed_articles(self, limit: int = 3) -> dict:
    parent_id = self.request.id
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        article_ids = _claim_next_pending_articles(cursor, limit=limit)
        connection.commit()
    finally:
        connection.close()

    if not article_ids:
        return {
            "status": "empty",
        }

    # Dispatch tasks asynchronously
    for article_id in article_ids:
        embed_article.delay(article_id=article_id, parent_task_id=parent_id)

    return {
        "status": "dispatched",
        "count": len(article_ids),
        "article_ids": article_ids,
    }


@celery_app.task(name="pipeline.tasks.embed.embed_backfill_articles")
def embed_backfill_articles(limit: int = 100, force: bool = False, parent_task_id: str | None = None) -> dict:
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        article_ids = _select_backfill_article_ids(cursor, limit=limit, force=force)
        connection.commit()
    finally:
        connection.close()

    if not article_ids:
        return {
            "status": "empty",
            "limit": limit,
            "force": force,
            "processed": 0,
        }

    results = []
    completed = 0
    failed = 0
    for article_id in article_ids:
        result = embed_article(article_id=article_id, parent_task_id=parent_task_id)
        results.append(result)
        if result.get("status") == "completed":
            completed += 1
        else:
            failed += 1

    return {
        "status": "completed" if failed == 0 else "partial",
        "limit": limit,
        "force": force,
        "processed": len(article_ids),
        "completed": completed,
        "failed": failed,
        "article_ids": article_ids,
        "results": results,
    }
