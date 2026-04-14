from pipeline.celery_app import celery_app
from pipeline.db import get_db_connection
from pipeline.domestic_taxonomy import (
    infer_domestic_category,
    infer_domestic_location,
    normalize_domestic_category,
)
from pipeline.llm_client import (
    extract_domestic_article_metadata,
    get_translation_model,
    is_llm_enabled,
    translate_article_content,
)


def _placeholder_translate_text(text: str | None, target_language: str) -> str | None:
    if not text:
        return None
    return f"[{target_language} placeholder] {text}"


def _placeholder_summary(content: str | None, target_language: str) -> str | None:
    if not content:
        return None
    compact = " ".join(content.split())
    if len(compact) > 280:
        compact = compact[:277] + "..."
    return f"[{target_language} summary placeholder] {compact}"


def _is_same_language_passthrough(source_language: str | None, target_language: str) -> bool:
    source = (source_language or "").strip().lower()
    target = (target_language or "").strip().lower()
    return source.startswith("zh") and target.startswith("zh")


def _normalized_domestic_metadata(title: str | None, content: str | None, section: str | None, raw_category: str | None) -> dict[str, str | None]:
    category = infer_domestic_category(title, content, section, raw_category)
    province, city = infer_domestic_location(title, content)
    return {
        "category": category,
        "province": province,
        "city": city,
        "company": None,
    }


def _set_translation_status(cursor, article_id: int, status: str):
    cursor.execute(
        """
        UPDATE articles
        SET translation_status = %s, updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (status, article_id),
    )


def _fetch_article(cursor, article_id: int):
    cursor.execute(
        """
        SELECT id, title_original, content_original, language, translation_status, section, category
        FROM articles
        WHERE id = %s
        """,
        (article_id,),
    )
    return cursor.fetchone()


def _claim_next_pending_articles(cursor, limit: int = 1):
    cursor.execute(
        """
        WITH candidate AS (
            SELECT id
            FROM articles
            WHERE translation_status = 'pending'
            ORDER BY publish_time DESC NULLS LAST, id DESC
            LIMIT %s
            FOR UPDATE SKIP LOCKED
        )
        UPDATE articles a
        SET translation_status = 'processing', updated_at = CURRENT_TIMESTAMP
        FROM candidate
        WHERE a.id = candidate.id
        RETURNING a.id
        """,
        (limit,),
    )
    return [row[0] for row in cursor.fetchall()]


def _select_backfill_article_ids(cursor, target_language: str, limit: int, force: bool = False) -> list[int]:
    if force:
        cursor.execute(
            """
            SELECT a.id
            FROM articles a
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
            WHERE a.translation_status IN ('pending', 'failed')
               OR NOT EXISTS (
                    SELECT 1
                    FROM article_translations t
                    WHERE t.article_id = a.id
                      AND t.target_language = %s
               )
            ORDER BY a.publish_time DESC NULLS LAST, a.id DESC
            LIMIT %s
            """,
            (target_language, limit),
        )
    return [row[0] for row in cursor.fetchall()]


def _upsert_translation(cursor, article_id: int, target_language: str, title_text: str | None, summary_text: str | None, content_text: str | None):
    cursor.execute(
        """
        INSERT INTO article_translations (
            article_id,
            target_language,
            title_translated,
            summary_translated,
            content_translated,
            translator,
            status,
            updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, 'completed', CURRENT_TIMESTAMP)
        ON CONFLICT (article_id, target_language) DO UPDATE SET
            title_translated = EXCLUDED.title_translated,
            summary_translated = EXCLUDED.summary_translated,
            content_translated = EXCLUDED.content_translated,
            translator = EXCLUDED.translator,
            status = 'completed',
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            article_id,
            target_language,
            title_text,
            summary_text,
            content_text,
            "placeholder-translator",
        ),
    )


def _upsert_translation_with_translator(
    cursor,
    article_id: int,
    target_language: str,
    title_text: str | None,
    summary_text: str | None,
    content_text: str | None,
    translator: str,
):
    cursor.execute(
        """
        INSERT INTO article_translations (
            article_id,
            target_language,
            title_translated,
            summary_translated,
            content_translated,
            translator,
            status,
            updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, 'completed', CURRENT_TIMESTAMP)
        ON CONFLICT (article_id, target_language) DO UPDATE SET
            title_translated = EXCLUDED.title_translated,
            summary_translated = EXCLUDED.summary_translated,
            content_translated = EXCLUDED.content_translated,
            translator = EXCLUDED.translator,
            status = 'completed',
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            article_id,
            target_language,
            title_text,
            summary_text,
            content_text,
            translator,
        ),
    )


@celery_app.task(name="pipeline.tasks.translate.translate_article")
def translate_article(article_id: int, target_language: str = "zh-CN", parent_task_id: str | None = None) -> dict:
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        article = _fetch_article(cursor, article_id)
        if not article:
            connection.rollback()
            return {
                "article_id": article_id,
                "target_language": target_language,
                "status": "not_found",
            }

        _set_translation_status(cursor, article_id, "processing")
        if _is_same_language_passthrough(article[3], target_language):
            metadata = _normalized_domestic_metadata(article[1], article[2], article[5], article[6])
            if is_llm_enabled():
                try:
                    extracted = extract_domestic_article_metadata(title=article[1], content=article[2])
                    metadata["category"] = normalize_domestic_category(extracted.get("category")) or metadata["category"]
                    metadata["province"] = (extracted.get("province") or "").strip() or metadata["province"]
                    metadata["city"] = (extracted.get("city") or "").strip() or metadata["city"]
                    metadata["company"] = (extracted.get("involved_companies") or "").strip() or metadata["company"]
                except Exception:
                    pass
            _upsert_translation_with_translator(
                cursor,
                article_id,
                target_language,
                article[1],
                None,
                article[2],
                "source-original",
            )
            if metadata["category"] or metadata["province"] or metadata["city"] or metadata["company"]:
                cursor.execute(
                    """
                    UPDATE articles
                    SET category = COALESCE(%s, category),
                        province = COALESCE(%s, province),
                        city = COALESCE(%s, city),
                        company = COALESCE(%s, company),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (metadata["category"], metadata["province"], metadata["city"], metadata["company"], article_id),
                )
            mode = "passthrough"
        elif is_llm_enabled():
            translated = translate_article_content(
                title=article[1],
                content=article[2],
                source_language=article[3],
                target_language=target_language,
            )
            normalized_category = normalize_domestic_category(translated.get("category"))
            _upsert_translation_with_translator(
                cursor,
                article_id,
                target_language,
                translated.get("title_translated"),
                translated.get("summary_translated"),
                translated.get("content_translated"),
                f"openai-compatible:{get_translation_model()}",
            )
            # 1. 优先尝试从 LLM 提取的分类中归一化
            extracted_category = normalized_category or None
            
            # 2. 兜底逻辑：如果 LLM 没提取出标准分类，利用翻译后的中文内容进行关键词推理
            if not extracted_category:
                extracted_category = infer_domestic_category(
                    title=translated.get("title_translated"),
                    content=translated.get("content_translated"),
                    section=article[5],
                    raw_category=article[6]
                )

            extracted_companies = translated.get("involved_companies") or None
            if extracted_category or extracted_companies:
                cursor.execute(
                    """
                    UPDATE articles
                    SET category = COALESCE(%s, category),
                        company = COALESCE(%s, company),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (extracted_category, extracted_companies, article_id),
                )
            mode = "llm"
        else:
            title_text = _placeholder_translate_text(article[1], target_language)
            summary_text = _placeholder_summary(article[2], target_language)
            content_text = _placeholder_translate_text(article[2], target_language)
            _upsert_translation(cursor, article_id, target_language, title_text, summary_text, content_text)
            mode = "placeholder"
        _set_translation_status(cursor, article_id, "completed")
        connection.commit()
        return {
            "article_id": article_id,
            "target_language": target_language,
            "status": "completed",
            "mode": mode,
        }
    except Exception as exc:
        connection.rollback()
        try:
            cursor = connection.cursor()
            _set_translation_status(cursor, article_id, "failed")
            connection.commit()
        except Exception:
            connection.rollback()
        return {
            "article_id": article_id,
            "target_language": target_language,
            "status": "failed",
            "error": str(exc),
        }
    finally:
        connection.close()


@celery_app.task(name="pipeline.tasks.translate.auto_translate_articles", bind=True)
def auto_translate_articles(self, limit: int = 3, target_language: str = "zh-CN") -> dict:
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
            "target_language": target_language,
            "status": "empty",
        }

    # Dispatch tasks asynchronously
    for article_id in article_ids:
        translate_article.delay(article_id=article_id, target_language=target_language, parent_task_id=parent_id)

    return {
        "status": "dispatched",
        "count": len(article_ids),
        "article_ids": article_ids,
        "target_language": target_language,
    }


@celery_app.task(name="pipeline.tasks.translate.translate_backfill_articles")
def translate_backfill_articles(target_language: str = "zh-CN", limit: int = 100, force: bool = False, parent_task_id: str | None = None) -> dict:
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        article_ids = _select_backfill_article_ids(
            cursor,
            target_language=target_language,
            limit=limit,
            force=force,
        )
        connection.commit()
    finally:
        connection.close()

    if not article_ids:
        return {
            "status": "empty",
            "target_language": target_language,
            "limit": limit,
            "force": force,
            "processed": 0,
        }

    results = []
    completed = 0
    failed = 0
    for article_id in article_ids:
        result = translate_article(article_id=article_id, target_language=target_language, parent_task_id=parent_task_id)
        results.append(result)
        if result.get("status") == "completed":
            completed += 1
        else:
            failed += 1

    return {
        "status": "completed" if failed == 0 else "partial",
        "target_language": target_language,
        "limit": limit,
        "force": force,
        "processed": len(article_ids),
        "completed": completed,
        "failed": failed,
        "article_ids": article_ids,
        "results": results,
    }
