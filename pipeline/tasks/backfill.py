from pipeline.celery_app import celery_app
from pipeline.db import get_db_connection
from pipeline.domestic_taxonomy import (
    infer_domestic_category,
    infer_domestic_location,
    normalize_domestic_category,
)
from pipeline.llm_client import extract_domestic_article_metadata, is_llm_enabled






@celery_app.task(name="pipeline.tasks.backfill.run_domestic_metadata_backfill", bind=True)
def run_domestic_metadata_backfill(
    self,
    limit: int = 100,
    force: bool = False,
    parent_task_id: str | None = None,
) -> dict:
    if not is_llm_enabled():
        return {"status": "skipped", "reason": "LLM not enabled"}

    effective_parent_id = parent_task_id or self.request.id
    connection = get_db_connection()
    try:
        cursor = connection.cursor()

        # Select domestic articles (language starts with 'zh')
        if force:
            cursor.execute(
                """
                SELECT id, title_original, content_original, section, category
                FROM articles
                WHERE language LIKE 'zh%%'
                ORDER BY publish_time DESC NULLS LAST, id DESC
                LIMIT %s
                """,
                (limit,),
            )
        else:
            # Only articles likely to be domestic that are missing some key metadata
            cursor.execute(
                """
                SELECT id, title_original, content_original, section, category
                FROM articles
                WHERE language LIKE 'zh%%'
                  AND (province IS NULL OR city IS NULL OR company IS NULL OR category IS NULL OR category = '其他')
                ORDER BY publish_time DESC NULLS LAST, id DESC
                LIMIT %s
                """,
                (limit,),
            )

        articles = cursor.fetchall()
        if not articles:
            return {
                "status": "empty",
                "processed": 0,
                "completed": 0,
                "failed": 0,
                "parent_task_id": effective_parent_id,
            }

        completed = 0
        failed = 0
        results = []

        for art_id, title, content, section, raw_cat in articles:
            try:
                # Rule-based fallback as baseline
                category = infer_domestic_category(title, content, section, raw_cat)
                province, city = infer_domestic_location(title, content)
                metadata = {
                    "category": category,
                    "province": province,
                    "city": city,
                    "company": None,
                }

                # LLM extraction
                try:
                    extracted = extract_domestic_article_metadata(title=title, content=content)
                    metadata["category"] = normalize_domestic_category(extracted.get("category")) or metadata["category"]
                    metadata["province"] = (extracted.get("province") or "").strip() or metadata["province"]
                    metadata["city"] = (extracted.get("city") or "").strip() or metadata["city"]
                    metadata["company"] = (extracted.get("involved_companies") or "").strip() or metadata["company"]
                except Exception:
                    # Fallback to rules is already set in metadata dict
                    pass

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
                    (metadata["category"], metadata["province"], metadata["city"], metadata["company"], art_id),
                )
                connection.commit()
                completed += 1
                results.append({"article_id": art_id, "status": "success"})
            except Exception as e:
                connection.rollback()
                failed += 1
                results.append({"article_id": art_id, "status": "failed", "error": str(e)})

        return {
            "status": "completed" if failed == 0 else "partial",
            "processed": len(articles),
            "completed": completed,
            "failed": failed,
            "parent_task_id": effective_parent_id,
            "results": results[:10],  # Return first 10 results for context
        }
    finally:
        connection.close()


@celery_app.task(name="pipeline.tasks.backfill.manual_global_processing", bind=True)
def manual_global_processing(self, limit: int = 100, force: bool = False, target_language: str = "zh-CN", parent_task_id: str | None = None) -> dict:
    """Manually triggered global translation and enrichment."""
    effective_parent_id = parent_task_id or self.request.id
    async_res = celery_app.send_task(
        "pipeline.tasks.translate.translate_backfill_articles",
        kwargs={
            "target_language": target_language,
            "limit": limit,
            "force": force,
            "parent_task_id": effective_parent_id,
        },
        queue="translate",
    )
    result = async_res.get(disable_sync_subtasks=False)
    return result


@celery_app.task(name="pipeline.tasks.backfill.manual_generate_embeddings", bind=True)
def manual_generate_embeddings(self, limit: int = 100, force: bool = False, parent_task_id: str | None = None) -> dict:
    """Manually triggered vectorization index generation."""
    effective_parent_id = parent_task_id or self.request.id
    async_res = celery_app.send_task(
        "pipeline.tasks.embed.embed_backfill_articles",
        kwargs={
            "limit": limit,
            "force": force,
            "parent_task_id": effective_parent_id,
        },
        queue="embed",
    )
    result = async_res.get(disable_sync_subtasks=False)
    return result
