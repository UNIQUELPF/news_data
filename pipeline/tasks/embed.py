import json

from pipeline.celery_app import celery_app
from pipeline.db import get_db_connection
from pipeline.llm_client import (
    embed_texts,
    get_embedding_model,
    get_embedding_provider,
    is_embedding_enabled,
)
from pipeline.qdrant_utils import get_qdrant_client, COLLECTION_NAME
from qdrant_client.http.models import PointStruct
import uuid


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
            a.content_plain,
            t.title_translated,
            t.summary_translated,
            t.content_translated,
            a.company,
            a.publish_time,
            a.category,
            a.country_code,
            a.language
        FROM articles a
        LEFT JOIN article_translations t
            ON t.article_id = a.id
           AND t.target_language = %s
        WHERE a.id = %s
        """,
        (target_language, article_id),
    )
    return cursor.fetchone()


import re

def _chunk_text(text: str | None, chunk_size: int = 1000, chunk_overlap: int = 200) -> list[str]:
    if not text:
        return []
    
    text = text.strip()
    if not text:
        return []

    # 1. 智能断句：按中英文标点、换行符切分，并保留切分符
    parts = re.split(r'([。！？\?\!]+|\n+|；|;|\.\s+)', text)
    
    sentences = []
    for i in range(0, len(parts) - 1, 2):
        sentence = parts[i] + parts[i+1]
        if sentence.strip():
            sentences.append(sentence.strip())
            
    # 兜底：处理剩余部分
    if len(parts) % 2 != 0 and parts[-1].strip():
        sentences.append(parts[-1].strip())
        
    chunks = []
    current_chunk = []
    current_length = 0

    # 2. 拼装分块并保留 Overlap
    for sentence in sentences:
        sentence_len = len(sentence)
        
        # 异常情况：单句极长，强制硬切
        if sentence_len > chunk_size:
            if current_chunk:
                chunks.append(" ".join(current_chunk))
                current_chunk = []
                current_length = 0
            
            for i in range(0, sentence_len, chunk_size - chunk_overlap):
                chunks.append(sentence[i:i+chunk_size])
            continue
            
        # 超出当前块容量时，结算并处理 Overlap
        if current_length + sentence_len > chunk_size and current_chunk:
            chunks.append(" ".join(current_chunk))
            
            overlap_chunk = []
            overlap_length = 0
            for s in reversed(current_chunk):
                if overlap_length + len(s) <= chunk_overlap:
                    overlap_chunk.insert(0, s)
                    overlap_length += len(s) + 1 # +1 是为了补上空格长度
                else:
                    break
            
            current_chunk = overlap_chunk
            current_length = overlap_length

        current_chunk.append(sentence)
        current_length += sentence_len + 1 

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks


def _upsert_embeddings(article_id: int, chunks: list[str], vectors: list[list[float]], metadata: dict):
    q_client = get_qdrant_client()
    points = []

    for chunk_index, (chunk_text, vector) in enumerate(zip(chunks, vectors)):
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"article_{article_id}_chunk_{chunk_index}"))
        payload = {
            "article_id": article_id,
            "chunk_index": chunk_index,
            "chunk_text": chunk_text,
            "company": metadata.get("company"),
            "country_code": metadata.get("country_code"),
            "language": metadata.get("language"),
            "publish_time": metadata.get("publish_time").isoformat() if metadata.get("publish_time") else None,
            "category": metadata.get("category"),
            "title": metadata.get("title")
        }
        points.append(PointStruct(id=point_id, vector=vector, payload=payload))

    if points:
        q_client.upsert(collection_name=COLLECTION_NAME, points=points)


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
        
        metadata = {
            "company": row[6],
            "publish_time": row[7],
            "category": row[8],
            "country_code": row[9],
            "language": row[10],
            "title": title_text
        }

        chunks = _chunk_text("\n\n".join(part for part in [title_text, content_text] if part))
        if is_embedding_enabled() and chunks:
            vectors, model_name = embed_texts(chunks)
            _upsert_embeddings(article_id, chunks, vectors, metadata)
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
