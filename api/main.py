import math
import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Query, Request
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel

from pipeline.celery_app import celery_app
from pipeline.db import get_db_connection
from pipeline.llm_client import embed_texts, get_pipeline_runtime_status, is_embedding_enabled
from pipeline.presets import PIPELINE_SPIDER_PRESETS
from pipeline.search_config import get_hybrid_ranking_weights
from pipeline.task_state import (
    append_pipeline_task_note as _append_pipeline_task_note_helper,
)
from pipeline.task_state import (
    ensure_pipeline_task_runs_table as _ensure_pipeline_task_runs_table_helper,
)
from pipeline.task_state import (
    record_pipeline_task as _record_pipeline_task_helper,
)
from pipeline.task_state import (
    sync_pipeline_task_state as _sync_pipeline_task_state_helper,
)
from pipeline.tasks.backfill import (
    run_domestic_metadata_backfill,
)

app = FastAPI(title="Global Political Economy API", version="0.1.0")
ADMIN_API_TOKEN = os.getenv("ADMIN_API_TOKEN", "").strip()


class DomesticProcessRequest(BaseModel):
    limit: int = 100
    force: bool = False

class GlobalProcessRequest(BaseModel):
    limit: int = 100
    force: bool = False
    target_language: str = "zh-CN"

class IngestRequest(BaseModel):
    spiders: list[str]

class EmbedRequest(BaseModel):
    limit: int = 100
    force: bool = False


def _require_admin_token(x_admin_token: Optional[str]):
    if not ADMIN_API_TOKEN:
        return
    if x_admin_token == ADMIN_API_TOKEN:
        return
    raise HTTPException(status_code=401, detail="Invalid admin token")


def _retryable_task_type(task_type: str) -> bool:
    return task_type in {"backfill", "pipeline_run"}


def _ensure_pipeline_task_runs_table():
    _ensure_pipeline_task_runs_table_helper()


def _resolve_request_ip(request: Request, x_forwarded_for: Optional[str]) -> Optional[str]:
    forwarded = (x_forwarded_for or "").strip()
    if forwarded:
        return forwarded.split(",")[0].strip() or None
    if request.client:
        return request.client.host
    return None


def _record_pipeline_task(
    task_id: str,
    task_name: str,
    task_type: str,
    params: dict,
    *,
    requested_by: Optional[str] = None,
    request_ip: Optional[str] = None,
    user_agent: Optional[str] = None,
):
    _record_pipeline_task_helper(
        task_id,
        task_name,
        task_type,
        params,
        requested_by=requested_by,
        request_ip=request_ip,
        user_agent=user_agent,
        state="PENDING",
    )


def _sync_pipeline_task_state(task_id: str, state: str, result=None):
    _sync_pipeline_task_state_helper(task_id, state, result)


def _append_pipeline_task_note(task_id: str, note: str):
    _append_pipeline_task_note_helper(task_id, note)


def _list_recent_pipeline_tasks(task_type: str = "backfill", limit: int = 10):
    _ensure_pipeline_task_runs_table()
    connection = get_db_connection()
    try:
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            """
            SELECT
                task_id,
                task_name,
                task_type,
                state,
                params,
                result,
                error_message,
                requested_by,
                request_ip,
                user_agent,
                created_at,
                updated_at
            FROM pipeline_task_runs
            WHERE task_type = %s
            ORDER BY created_at DESC, id DESC
            LIMIT %s
            """,
            (task_type, limit),
        )
        return cursor.fetchall()
    finally:
        connection.close()


def _crawl_monitor_summary():
    connection = get_db_connection()
    try:
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            """
            SELECT
                COUNT(*) FILTER (WHERE started_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours') AS crawl_jobs_24h,
                COUNT(*) FILTER (
                    WHERE started_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
                      AND status = 'success'
                ) AS crawl_success_24h,
                COUNT(*) FILTER (
                    WHERE started_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
                      AND status = 'failed'
                ) AS crawl_failed_24h,
                COALESCE(SUM(items_scraped) FILTER (
                    WHERE started_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
                ), 0) AS items_scraped_24h,
                COUNT(*) FILTER (WHERE status = 'running') AS crawl_running_now
            FROM crawl_jobs
            """
        )
        summary = cursor.fetchone()
        cursor.execute(
            """
            SELECT spider_name, status, items_scraped, started_at, finished_at
            FROM crawl_jobs
            ORDER BY started_at DESC, id DESC
            LIMIT 5
            """
        )
        summary["latest_crawls"] = cursor.fetchall()
        cursor.execute(
            """
            SELECT
                spider_name,
                COUNT(*) AS failed_count
            FROM crawl_jobs
            WHERE started_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
              AND status = 'failed'
            GROUP BY spider_name
            ORDER BY failed_count DESC, spider_name ASC
            LIMIT 5
            """
        )
        summary["failed_spiders_24h"] = cursor.fetchall()
        cursor.execute(
            """
            SELECT
                spider_name,
                COUNT(*) FILTER (WHERE status = 'success') AS success_count,
                COUNT(*) FILTER (WHERE status = 'failed') AS failed_count,
                COUNT(*) AS total_count,
                ROUND(
                    100.0 * COUNT(*) FILTER (WHERE status = 'success') / NULLIF(COUNT(*), 0),
                    1
                ) AS success_rate
            FROM crawl_jobs
            WHERE started_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
            GROUP BY spider_name
            ORDER BY total_count DESC, spider_name ASC
            LIMIT 5
            """
        )
        summary["spider_health_24h"] = cursor.fetchall()
        cursor.execute(
            """
            SELECT
                spider_name,
                started_at,
                finished_at,
                items_scraped,
                error_message
            FROM crawl_jobs
            WHERE status = 'failed'
            ORDER BY started_at DESC, id DESC
            LIMIT 5
            """
        )
        summary["recent_failures"] = cursor.fetchall()
        return summary
    finally:
        connection.close()


def _get_pipeline_task(task_id: str):
    _ensure_pipeline_task_runs_table()
    connection = get_db_connection()
    try:
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            """
            SELECT
                task_id,
                task_name,
                task_type,
                state,
                params,
                result,
                error_message,
                requested_by,
                request_ip,
                user_agent,
                created_at,
                updated_at
            FROM pipeline_task_runs
            WHERE task_id = %s
            """,
            (task_id,),
        )
        return cursor.fetchone()
    finally:
        connection.close()


def _pipeline_task_monitor_summary():
    _ensure_pipeline_task_runs_table()
    connection = get_db_connection()
    try:
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            """
            SELECT
                COUNT(*) FILTER (WHERE state = 'PENDING') AS pending_tasks,
                COUNT(*) FILTER (WHERE state = 'STARTED') AS started_tasks,
                COUNT(*) FILTER (WHERE state = 'RETRY') AS retry_tasks,
                COUNT(*) FILTER (
                    WHERE task_type = 'backfill'
                      AND state IN ('PENDING', 'STARTED', 'RETRY')
                ) AS backfill_active,
                COUNT(*) FILTER (
                    WHERE task_type = 'pipeline_run'
                      AND state IN ('PENDING', 'STARTED', 'RETRY')
                ) AS pipeline_run_active
            FROM pipeline_task_runs
            """
        )
        return cursor.fetchone()
    finally:
        connection.close()


def _time_range_to_since(time_range: str | None) -> Optional[datetime]:
    if not time_range or time_range == "all":
        return None

    now = datetime.now()
    mapping = {
        "1d": now - timedelta(days=1),
        "3d": now - timedelta(days=3),
        "7d": now - timedelta(days=7),
        "1m": now - timedelta(days=30),
        "6m": now - timedelta(days=180),
        "1y": now - timedelta(days=365),
    }
    return mapping.get(time_range)


def _normalize_empty(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = value.strip()
    return value or None


MEGA_ORGANIZATIONS = {
    "金砖国家": ["BRA", "RUS", "IND", "CHN", "ZAF", "EGY", "ETH", "IRN", "ARE"],
    "二十国集团": ["ARG", "AUS", "BRA", "CAN", "CHN", "FRA", "DEU", "IND", "IDN", "ITA", "JPN", "KOR", "MEX", "RUS", "SAU", "ZAF", "TUR", "GBR", "USA"],
    "七国集团": ["CAN", "FRA", "DEU", "ITA", "JPN", "GBR", "USA"],
    "亚太经济合作组织": ["AUS", "BRN", "CAN", "CHL", "CHN", "HKG", "IDN", "JPN", "KOR", "MYS", "MEX", "NZL", "PNG", "PER", "PHL", "RUS", "SGP", "TWN", "THA", "USA", "VNM"],
    "欧盟": ["AUT", "BEL", "BGR", "HRV", "CYP", "CZE", "DNK", "EST", "FIN", "FRA", "DEU", "GRC", "HUN", "IRL", "ITA", "LVA", "LTU", "LUX", "MLT", "NLD", "POL", "PRT", "ROU", "SVK", "SVN", "ESP", "SWE"],
    "东盟": ["BRN", "KHM", "IDN", "LAO", "MYS", "MMR", "PHL", "SGP", "THA", "VNM"],
    "非盟": ["DZA", "EGY", "ETH", "NGA", "ZAF", "AGO", "BEN", "BWA", "BFA", "BDI", "CMR", "CPV", "CAF", "TCD", "COM", "COD", "DJI", "GNQ", "ERI", "GAB", "GMB", "GHA", "GIN", "GNB", "CIV", "KEN", "LSO", "LBR", "LBY", "MDG", "MWI", "MLI", "MRT", "MUS", "MAR", "MOZ", "NAM", "NER", "RWA", "STP", "SEN", "SYC", "SLE", "SOM", "SSD", "SDN", "SWZ", "TZA", "TGO", "TUN", "UGA", "ZMB", "ZWE"],
    "石油输出国组织": ["DZA", "AGO", "GNQ", "GAB", "IRN", "IRQ", "KWT", "LBY", "NGA", "SAU", "ARE", "VEN"]
}

def _build_filter_conditions(
    *,
    category: Optional[str],
    country: Optional[str],
    country_code: Optional[str],
    organization: Optional[str],
    company: Optional[str],
    province: Optional[str] = None,
    city: Optional[str] = None,
    time_range: Optional[str] = None,
    alias: str = "a",
):
    conditions = []
    params: list = []

    category = _normalize_empty(category)
    if category and category != "all":
        conditions.append(f"{alias}.category LIKE %s")
        params.append(f"%{category}%")

    country_code = _normalize_empty(country_code)
    if country_code and country_code != "all":
        conditions.append(f"{alias}.country_code = %s")
        params.append(country_code)

    country = _normalize_empty(country)
    if country and country != "all":
        conditions.append(f"{alias}.country = %s")
        params.append(country)

    organization = _normalize_empty(organization)
    if organization and organization != "all":
        if organization in MEGA_ORGANIZATIONS:
            codes = MEGA_ORGANIZATIONS[organization]
            conditions.append(f"({alias}.country_code = ANY(%s) OR {alias}.organization = %s)")
            params.extend([list(codes), organization])
        else:
            conditions.append(f"{alias}.organization = %s")
            params.append(organization)

    company = _normalize_empty(company)
    if company and company != "all":
        conditions.append(f"{alias}.company ILIKE %s")
        params.append(f"%{company}%")

    province = _normalize_empty(province)
    if province and province != "all":
        conditions.append(f"{alias}.province = %s")
        params.append(province)

    city = _normalize_empty(city)
    if city and city != "all":
        conditions.append(f"{alias}.city = %s")
        params.append(city)

    since = _time_range_to_since(time_range)
    if since:
        conditions.append(f"{alias}.publish_time >= %s")
        params.append(since)

    return conditions, params


def _build_keyword_condition(search_term: Optional[str], alias: str = "a"):
    if not search_term:
        return None, []

    like = f"%{search_term}%"
    return (
        f"""
        (
            {alias}.title_original ILIKE %s OR
            {alias}.content_original ILIKE %s OR
            {alias}.country ILIKE %s OR
            {alias}.organization ILIKE %s OR
            COALESCE({alias}.company, '') ILIKE %s OR
            COALESCE({alias}.province, '') ILIKE %s OR
            COALESCE({alias}.city, '') ILIKE %s OR
            EXISTS (
                SELECT 1
                FROM article_translations t
                WHERE t.article_id = {alias}.id
                  AND (
                    t.title_translated ILIKE %s OR
                    t.summary_translated ILIKE %s OR
                    t.content_translated ILIKE %s
                  )
            )
        )
        """,
        [like, like, like, like, like, like, like, like, like, like],
    )


def _build_keyword_score_expr(alias: str = "a") -> str:
    return f"""
        (
            CASE WHEN {alias}.title_original ILIKE %s THEN 3 ELSE 0 END +
            CASE WHEN {alias}.content_original ILIKE %s THEN 1 ELSE 0 END +
            CASE WHEN {alias}.country ILIKE %s THEN 2 ELSE 0 END +
            CASE WHEN {alias}.organization ILIKE %s THEN 2 ELSE 0 END +
            CASE WHEN COALESCE({alias}.company, '') ILIKE %s THEN 2 ELSE 0 END +
            CASE WHEN COALESCE({alias}.province, '') ILIKE %s THEN 1 ELSE 0 END +
            CASE WHEN COALESCE({alias}.city, '') ILIKE %s THEN 1 ELSE 0 END +
            CASE WHEN COALESCE(t.title_translated, '') ILIKE %s THEN 3 ELSE 0 END +
            CASE WHEN COALESCE(t.summary_translated, '') ILIKE %s THEN 2 ELSE 0 END +
            CASE WHEN COALESCE(t.content_translated, '') ILIKE %s THEN 1 ELSE 0 END
        )
    """


def _get_dynamic_organizations(country_code: str | None) -> str:
    if not country_code:
        return ""
    
    matched = []
    for org_name, members in MEGA_ORGANIZATIONS.items():
        if country_code in members:
            matched.append(org_name)
    
    return ",".join(matched)


def _base_article_select(extra_columns: str = "") -> str:
    extra = f", {extra_columns}" if extra_columns else ""
    return f"""
        SELECT
            a.id,
            COALESCE(t.title_translated, a.title_original) AS title,
            a.title_original,
            a.category,
            a.country,
            '' AS organization, -- We calculate this dynamically now
            a.company,
            a.province,
            a.city,
            a.country_code,
            COALESCE(t.summary_translated, LEFT(a.content_original, 280)) AS summary,
            a.publish_time,
            a.source_url,
            s.display_name AS source_name,
            a.translation_status,
            a.embedding_status
            {extra}
        FROM articles a
        JOIN sources s ON s.id = a.source_id
        LEFT JOIN article_translations t
            ON t.article_id = a.id
           AND t.target_language = 'zh-CN'
    """


def _normalize_vector(value) -> list[float]:
    if value is None:
        return []
    if isinstance(value, list):
        return [float(item) for item in value]
    return [float(item) for item in list(value)]


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def _semantic_search_candidates(
    *,
    search_term: str,
    category: Optional[str],
    country: Optional[str],
    country_code: Optional[str],
    organization: Optional[str],
    company: Optional[str],
    province: Optional[str] = None,
    city: Optional[str] = None,
    time_range: Optional[str] = None,
    semantic_limit: int = 300,
):
    if not is_embedding_enabled():
        raise HTTPException(status_code=400, detail="Semantic search is unavailable: embedding provider is not configured")

    query_vectors, model_name = embed_texts([search_term])
    if not query_vectors:
        return []
    query_vector = query_vectors[0]

    conditions, params = _build_filter_conditions(
        category=category,
        country=country,
        country_code=country_code,
        organization=organization,
        company=company,
        province=province,
        city=city,
        time_range=time_range,
        alias="a",
    )
    conditions.append("e.embedding_model = %s")
    params.append(model_name)

    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    connection = get_db_connection()
    try:
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            f"""
            {_base_article_select("e.embedding_vector, e.chunk_index")}
            JOIN article_embeddings e ON e.article_id = a.id
            {where_sql}
            ORDER BY a.publish_time DESC NULLS LAST, a.id DESC, e.chunk_index ASC
            LIMIT %s
            """,
            params + [semantic_limit],
        )
        rows = cursor.fetchall()
    finally:
        connection.close()

    best_by_article: dict[int, dict] = {}
    for row in rows:
        vector = _normalize_vector(row.pop("embedding_vector"))
        score = _cosine_similarity(query_vector, vector)
        article_id = row["id"]
        existing = best_by_article.get(article_id)
        if not existing or score > existing["semantic_score"]:
            row["semantic_score"] = score
            best_by_article[article_id] = row

    ranked = sorted(best_by_article.values(), key=lambda item: (item["semantic_score"], item["publish_time"] or datetime.min), reverse=True)
    return ranked


def _get_article_embedding_vectors(article_id: int) -> tuple[str | None, list[list[float]]]:
    connection = get_db_connection()
    try:
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            """
            SELECT embedding_model, embedding_vector, chunk_index
            FROM article_embeddings
            WHERE article_id = %s
            ORDER BY embedding_model, chunk_index
            """,
            (article_id,),
        )
        rows = cursor.fetchall()
    finally:
        connection.close()

    if not rows:
        return None, []

    model_name = rows[0]["embedding_model"]
    vectors = [_normalize_vector(row["embedding_vector"]) for row in rows if row["embedding_model"] == model_name]
    return model_name, vectors


def _similar_articles(article_id: int, limit: int = 5, candidate_limit: int = 800):
    model_name, target_vectors = _get_article_embedding_vectors(article_id)
    if not model_name or not target_vectors:
        return []

    connection = get_db_connection()
    try:
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            f"""
            {_base_article_select("e.embedding_vector, e.chunk_index, e.embedding_model")}
            JOIN article_embeddings e ON e.article_id = a.id
            WHERE a.id <> %s
              AND e.embedding_model = %s
            ORDER BY a.publish_time DESC NULLS LAST, a.id DESC, e.chunk_index ASC
            LIMIT %s
            """,
            (article_id, model_name, candidate_limit),
        )
        rows = cursor.fetchall()
    finally:
        connection.close()

    best_by_article: dict[int, dict] = {}
    for row in rows:
        candidate_vector = _normalize_vector(row.pop("embedding_vector"))
        row.pop("embedding_model", None)
        score = max((_cosine_similarity(target_vector, candidate_vector) for target_vector in target_vectors), default=0.0)
        existing = best_by_article.get(row["id"])
        if not existing or score > existing["similarity_score"]:
            row["similarity_score"] = score
            best_by_article[row["id"]] = row

    return sorted(
        best_by_article.values(),
        key=lambda item: (item["similarity_score"], item["publish_time"] or datetime.min),
        reverse=True,
    )[:limit]


def _keyword_search_candidates(
    *,
    search_term: Optional[str],
    category: Optional[str],
    country: Optional[str],
    country_code: Optional[str],
    organization: Optional[str],
    company: Optional[str],
    province: Optional[str] = None,
    city: Optional[str] = None,
    time_range: Optional[str] = None,
):
    conditions, params = _build_filter_conditions(
        category=category,
        country=country,
        country_code=country_code,
        organization=organization,
        company=company,
        province=province,
        city=city,
        time_range=time_range,
        alias="a",
    )

    score_expr = "0"
    score_params: list = []
    if search_term:
        keyword_condition, keyword_params = _build_keyword_condition(search_term, alias="a")
        if keyword_condition:
            conditions.append(keyword_condition)
            params.extend(keyword_params)
            like = f"%{search_term}%"
            score_expr = _build_keyword_score_expr("a")
            score_params = [like, like, like, like, like, like, like, like, like, like]

    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    connection = get_db_connection()
    try:
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            f"""
            {_base_article_select(f"{score_expr} AS keyword_score")}
            {where_sql}
            ORDER BY keyword_score DESC, a.publish_time DESC NULLS LAST, a.id DESC
            """,
            score_params + params,
        )
        return cursor.fetchall()
    finally:
        connection.close()


def _paginate_items(items: list[dict], page: int, page_size: int):
    total = len(items)
    offset = (page - 1) * page_size
    return {
        "items": items[offset : offset + page_size],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": (total + page_size - 1) // page_size if total else 0,
        },
    }


def _hybrid_rank_items(keyword_items: list[dict], semantic_items: list[dict]) -> list[dict]:
    weights = get_hybrid_ranking_weights()
    merged: dict[int, dict] = {}

    for item in keyword_items:
        row = dict(item)
        row.setdefault("keyword_score", 0)
        row.setdefault("semantic_score", 0.0)
        merged[row["id"]] = row

    for item in semantic_items:
        row = merged.get(item["id"], dict(item))
        row["semantic_score"] = item.get("semantic_score", 0.0)
        row.setdefault("keyword_score", 0)
        merged[row["id"]] = row

    return sorted(
        merged.values(),
        key=lambda item: (
            float(item.get("keyword_score", 0)) * weights["keyword"] + float(item.get("semantic_score", 0.0)) * weights["semantic"],
            item.get("publish_time") or datetime.min,
        ),
        reverse=True,
    )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/v1/filters")
def get_filters():
    connection = get_db_connection()
    try:
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            """
            SELECT
                ARRAY(
                    SELECT DISTINCT TRIM(unnest(string_to_array(category, ',')))
                    FROM articles
                    WHERE category IS NOT NULL AND category <> ''
                    ORDER BY 1
                ) AS categories,
                ARRAY(
                    SELECT DISTINCT country
                    FROM articles
                    WHERE country IS NOT NULL AND country <> ''
                    ORDER BY country
                ) AS countries,
                ARRAY(
                    SELECT DISTINCT company
                    FROM articles
                    WHERE company IS NOT NULL AND company <> ''
                    ORDER BY company
                ) AS companies,
                ARRAY(
                    SELECT DISTINCT province
                    FROM articles
                    WHERE province IS NOT NULL AND province <> ''
                    ORDER BY province
                ) AS provinces,
                ARRAY(
                    SELECT DISTINCT city
                    FROM articles
                    WHERE city IS NOT NULL AND city <> ''
                    ORDER BY city
                ) AS cities
            """
        )
        row = cursor.fetchone()
        
        # Only use the fixed MEGA_ORGANIZATIONS as per design
        row["organizations"] = list(MEGA_ORGANIZATIONS.keys())
        
        return row
    finally:
        connection.close()


@app.get("/api/v1/articles")
def list_articles(
    q: Optional[str] = Query(default=None, description="Search in title/content/country/organization"),
    category: Optional[str] = None,
    country: Optional[str] = None,
    country_code: Optional[str] = Query(default=None, pattern="^[A-Z]{2,3}$"),
    organization: Optional[str] = None,
    company: Optional[str] = None,
    province: Optional[str] = None,
    city: Optional[str] = None,
    time_range: Optional[str] = Query(default="all", pattern="^(all|1d|3d|7d|1m|6m|1y)$"),
    search_mode: str = Query(default="keyword", pattern="^(keyword|semantic|hybrid)$"),
    semantic_limit: int = Query(default=300, ge=10, le=2000),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
):
    search_term = _normalize_empty(q)
    country_code = country_code if isinstance(country_code, str) else None
    province = province if isinstance(province, str) else None
    city = city if isinstance(city, str) else None
    if search_mode == "keyword" or not search_term:
        items = _keyword_search_candidates(
            search_term=search_term,
            category=category,
            country=country,
            country_code=country_code,
            organization=organization,
            company=company,
            province=province,
            city=city,
            time_range=time_range,
        )
        result = _paginate_items(items, page, page_size)
        # 动态计算组织
        for item in result["items"]:
            item["organization"] = _get_dynamic_organizations(item.get("country_code"))
            
        result["search"] = {
            "mode": "keyword",
            "query": search_term,
        }
        return result

    if search_mode == "semantic":
        items = _semantic_search_candidates(
            search_term=search_term,
            category=category,
            country=country,
            country_code=country_code,
            organization=organization,
            company=company,
            province=province,
            city=city,
            time_range=time_range,
            semantic_limit=semantic_limit,
        )
        result = _paginate_items(items, page, page_size)
        # 动态计算组织
        for item in result["items"]:
            item["organization"] = _get_dynamic_organizations(item.get("country_code"))

        result["search"] = {
            "mode": "semantic",
            "query": search_term,
        }
        return result

    keyword_items = _keyword_search_candidates(
        search_term=search_term,
        category=category,
        country=country,
        country_code=country_code,
        organization=organization,
        company=company,
        province=province,
        city=city,
        time_range=time_range,
    )
    semantic_items = _semantic_search_candidates(
        search_term=search_term,
        category=category,
        country=country,
        country_code=country_code,
        organization=organization,
        company=company,
        province=province,
        city=city,
        time_range=time_range,
        semantic_limit=semantic_limit,
    )

    ranked = _hybrid_rank_items(keyword_items, semantic_items)
    result = _paginate_items(ranked, page, page_size)
    # 动态计算组织
    for item in result["items"]:
        item["organization"] = _get_dynamic_organizations(item.get("country_code"))

    result["search"] = {
        "mode": "hybrid",
        "query": search_term,
        "weights": get_hybrid_ranking_weights(),
    }
    return result


@app.get("/api/v1/articles/{article_id}")
def get_article(article_id: int):
    connection = get_db_connection()
    try:
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            """
            SELECT
                a.id,
                a.source_url,
                a.title_original,
                a.content_original,
                a.publish_time,
                a.author,
                a.language,
                a.section,
                a.country,
                a.organization,
                a.company,
                a.province,
                a.city,
                a.category,
                a.country_code,
                a.translation_status,
                a.embedding_status,
                s.display_name AS source_name,
                t.target_language,
                t.title_translated,
                t.summary_translated,
                t.content_translated,
                t.status AS translation_record_status
            FROM articles a
            JOIN sources s ON s.id = a.source_id
            LEFT JOIN article_translations t
                ON t.article_id = a.id
               AND t.target_language = 'zh-CN'
            WHERE a.id = %s
            """,
            (article_id,),
        )
        article = cursor.fetchone()
        if not article:
            raise HTTPException(status_code=404, detail="Article not found")

        # 动态计算组织
        article["organization"] = _get_dynamic_organizations(article.get("country_code"))

        cursor.execute(
            """
            SELECT chunk_index, content_text, token_count, embedding_status
            FROM article_chunks
            WHERE article_id = %s
            ORDER BY chunk_index
            """,
            (article_id,),
        )
        chunks = cursor.fetchall()
        return {
            "article": article,
            "chunks": chunks,
            "similar_articles": _similar_articles(article_id),
        }
    finally:
        connection.close()


@app.get("/api/v1/pipeline/summary")
def pipeline_summary(x_admin_token: Optional[str] = Header(default=None)):
    _require_admin_token(x_admin_token)
    connection = get_db_connection()
    try:
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            """
            SELECT
                COUNT(*) AS total_articles,
                COUNT(*) FILTER (WHERE translation_status = 'pending') AS translation_pending,
                COUNT(*) FILTER (WHERE translation_status = 'processing') AS translation_processing,
                COUNT(*) FILTER (WHERE translation_status = 'completed') AS translation_completed,
                COUNT(*) FILTER (WHERE translation_status = 'failed') AS translation_failed,
                COUNT(*) FILTER (WHERE embedding_status = 'pending') AS embedding_pending,
                COUNT(*) FILTER (WHERE embedding_status = 'processing') AS embedding_processing,
                COUNT(*) FILTER (WHERE embedding_status = 'completed') AS embedding_completed,
                COUNT(*) FILTER (WHERE embedding_status = 'failed') AS embedding_failed
            FROM articles
            """
        )
        return cursor.fetchone()
    finally:
        connection.close()


@app.get("/api/v1/pipeline/monitor")
def pipeline_monitor(x_admin_token: Optional[str] = Header(default=None)):
    _require_admin_token(x_admin_token)
    return {
        "pipeline": pipeline_summary(x_admin_token=x_admin_token),
        "crawl": _crawl_monitor_summary(),
        "tasks": _pipeline_task_monitor_summary(),
    }


@app.post("/api/v1/pipeline/ingest")
def trigger_ingest(
    request: IngestRequest,
    http_request: Request,
    x_admin_token: Optional[str] = Header(default=None),
    x_admin_actor: Optional[str] = Header(default=None),
    user_agent: Optional[str] = Header(default=None),
    x_forwarded_for: Optional[str] = Header(default=None),
):
    _require_admin_token(x_admin_token)
    from pipeline.tasks.crawl import manual_ingest_from_spiders
    task = manual_ingest_from_spiders.delay(spiders=request.spiders)
    _record_pipeline_task(
        task_id=task.id,
        task_name="pipeline.tasks.crawl.manual_ingest_from_spiders",
        task_type="pipeline_run",
        params=request.model_dump(),
        requested_by=(x_admin_actor or "").strip() or None,
        request_ip=_resolve_request_ip(http_request, x_forwarded_for),
        user_agent=(user_agent or "").strip() or None,
    )
    return {"task_id": task.id, "status": "queued"}


@app.post("/api/v1/pipeline/process/global")
def trigger_global_process(
    request: GlobalProcessRequest,
    http_request: Request,
    x_admin_token: Optional[str] = Header(default=None),
    x_admin_actor: Optional[str] = Header(default=None),
    user_agent: Optional[str] = Header(default=None),
    x_forwarded_for: Optional[str] = Header(default=None),
):
    _require_admin_token(x_admin_token)
    from pipeline.tasks.backfill import manual_global_processing
    task = manual_global_processing.delay(
        limit=request.limit,
        force=request.force,
        target_language=request.target_language
    )
    _record_pipeline_task(
        task_id=task.id,
        task_name="pipeline.tasks.backfill.manual_global_processing",
        task_type="backfill",
        params=request.model_dump(),
        requested_by=(x_admin_actor or "").strip() or None,
        request_ip=_resolve_request_ip(http_request, x_forwarded_for),
        user_agent=(user_agent or "").strip() or None,
    )
    return {"task_id": task.id, "status": "queued"}


@app.post("/api/v1/pipeline/process/domestic")
def trigger_domestic_process(
    request: DomesticProcessRequest,
    http_request: Request,
    x_admin_token: Optional[str] = Header(default=None),
    x_admin_actor: Optional[str] = Header(default=None),
    user_agent: Optional[str] = Header(default=None),
    x_forwarded_for: Optional[str] = Header(default=None),
):
    _require_admin_token(x_admin_token)
    from pipeline.tasks.backfill import run_domestic_metadata_backfill
    task = run_domestic_metadata_backfill.delay(
        limit=request.limit,
        force=request.force
    )
    _record_pipeline_task(
        task_id=task.id,
        task_name="pipeline.tasks.backfill.run_domestic_metadata_backfill",
        task_type="backfill",
        params=request.model_dump(),
        requested_by=(x_admin_actor or "").strip() or None,
        request_ip=_resolve_request_ip(http_request, x_forwarded_for),
        user_agent=(user_agent or "").strip() or None,
    )
    return {"task_id": task.id, "status": "queued"}


@app.post("/api/v1/pipeline/process/embed")
def trigger_embed_process(
    request: EmbedRequest,
    http_request: Request,
    x_admin_token: Optional[str] = Header(default=None),
    x_admin_actor: Optional[str] = Header(default=None),
    user_agent: Optional[str] = Header(default=None),
    x_forwarded_for: Optional[str] = Header(default=None),
):
    _require_admin_token(x_admin_token)
    from pipeline.tasks.backfill import manual_generate_embeddings
    task = manual_generate_embeddings.delay(
        limit=request.limit,
        force=request.force
    )
    _record_pipeline_task(
        task_id=task.id,
        task_name="pipeline.tasks.backfill.manual_generate_embeddings",
        task_type="backfill",
        params=request.model_dump(),
        requested_by=(x_admin_actor or "").strip() or None,
        request_ip=_resolve_request_ip(http_request, x_forwarded_for),
        user_agent=(user_agent or "").strip() or None,
    )
    return {"task_id": task.id, "status": "queued"}


@app.get("/api/v1/pipeline/presets")
def list_pipeline_presets(x_admin_token: Optional[str] = Header(default=None)):
    _require_admin_token(x_admin_token)
    return {
        "items": PIPELINE_SPIDER_PRESETS
    }


@app.get("/api/v1/pipeline/tasks/{task_id}")
def get_task_status(task_id: str, x_admin_token: Optional[str] = Header(default=None)):
    _require_admin_token(x_admin_token)
    task_record = _get_pipeline_task(task_id)
    if not task_record:
        raise HTTPException(status_code=404, detail="Task not found")

    async_result = celery_app.AsyncResult(task_id)
    state = task_record["state"]
    if state == "PENDING" and async_result.state != "PENDING":
        state = async_result.state

    result = task_record.get("result")
    error_message = task_record.get("error_message")
    if async_result.successful() and async_result.result is not None:
        result = async_result.result
    elif async_result.failed() and async_result.result is not None:
        error_message = str(async_result.result)

    actions = {
        "can_cancel": state in {"PENDING", "STARTED", "RETRY"},
        "can_retry": state not in {"PENDING", "STARTED", "RETRY", "SUCCESS"} and _retryable_task_type(task_record["task_type"]),
    }

    return {
        "task_id": task_id,
        "task_name": task_record["task_name"],
        "task_type": task_record["task_type"],
        "state": state,
        "params": task_record.get("params"),
        "result": result,
        "error": error_message,
        "requested_by": task_record.get("requested_by"),
        "request_ip": task_record.get("request_ip"),
        "user_agent": task_record.get("user_agent"),
        "created_at": task_record.get("created_at"),
        "updated_at": task_record.get("updated_at"),
        "actions": actions,
    }


@app.post("/api/v1/pipeline/tasks/{task_id}/cancel")
def cancel_pipeline_task(
    task_id: str,
    http_request: Request,
    x_admin_token: Optional[str] = Header(default=None),
    x_admin_actor: Optional[str] = Header(default=None),
    user_agent: Optional[str] = Header(default=None),
    x_forwarded_for: Optional[str] = Header(default=None),
):
    _require_admin_token(x_admin_token)
    task_record = _get_pipeline_task(task_id)
    if not task_record:
        raise HTTPException(status_code=404, detail="Task not found")

    async_result = celery_app.AsyncResult(task_id)
    celery_state = async_result.state
    
    # If Celery says the task is already in a terminal state but DB thinks it's active,
    # just sync the DB and return success instead of 409.
    if celery_state in {"SUCCESS", "FAILURE", "REVOKED"}:
        db_state = task_record.get("state")
        if db_state in {"PENDING", "STARTED", "RETRY"}:
            _sync_pipeline_task_state(task_id, celery_state)
            return {
                "task_id": task_id,
                "state": celery_state,
                "status": "already_terminated",
                "synced": True
            }
        raise HTTPException(status_code=409, detail=f"Task is already in terminal state {celery_state}")

    celery_app.control.revoke(task_id, terminate=True)
    actor = (x_admin_actor or "").strip() or "unknown"
    request_ip = _resolve_request_ip(http_request, x_forwarded_for) or "unknown"
    audit_note = f"[cancel] by={actor} ip={request_ip} ua={(user_agent or '').strip() or 'unknown'}"
    _sync_pipeline_task_state(task_id, "REVOKED", {"cancelled": True, "cancelled_by": actor})
    _append_pipeline_task_note(task_id, audit_note)
    return {
        "task_id": task_id,
        "state": "REVOKED",
        "status": "cancelled",
    }


@app.post("/api/v1/pipeline/tasks/{task_id}/retry")
def retry_pipeline_task(
    task_id: str,
    http_request: Request,
    x_admin_token: Optional[str] = Header(default=None),
    x_admin_actor: Optional[str] = Header(default=None),
    user_agent: Optional[str] = Header(default=None),
    x_forwarded_for: Optional[str] = Header(default=None),
):
    _require_admin_token(x_admin_token)
    task_record = _get_pipeline_task(task_id)
    if not task_record:
        raise HTTPException(status_code=404, detail="Task not found")
    if not _retryable_task_type(task_record["task_type"]):
        raise HTTPException(status_code=400, detail="Only backfill and pipeline_run tasks can be retried")

    async_result = celery_app.AsyncResult(task_id)
    if async_result.state in {"PENDING", "STARTED", "RETRY"}:
        raise HTTPException(status_code=409, detail=f"Task is still active in state {async_result.state}")

    params = task_record.get("params") or {}
    t_name = task_record["task_name"]
    from pipeline.tasks.backfill import manual_global_processing, manual_generate_embeddings, run_domestic_metadata_backfill
    from pipeline.tasks.crawl import manual_ingest_from_spiders

    if t_name == "pipeline.tasks.backfill.manual_global_processing":
        new_task = manual_global_processing.delay(
            limit=params.get("limit", 100),
            force=params.get("force", False),
            target_language=params.get("target_language", "zh-CN")
        )
    elif t_name == "pipeline.tasks.backfill.manual_generate_embeddings":
        new_task = manual_generate_embeddings.delay(
            limit=params.get("limit", 100),
            force=params.get("force", False)
        )
    elif t_name == "pipeline.tasks.backfill.run_domestic_metadata_backfill":
        new_task = run_domestic_metadata_backfill.delay(
            limit=params.get("limit", 100),
            force=params.get("force", False)
        )
    elif t_name == "pipeline.tasks.crawl.manual_ingest_from_spiders":
        new_task = manual_ingest_from_spiders.delay(
            spiders=params.get("spiders", [])
        )
    else:
        # Fallback to old pipeline/backfill logic if still in DB but paths changed
        # We can just use the name from record but it might fail if imports changed
        raise HTTPException(status_code=400, detail="Cannot retry legacy tasks with this API version")
    
    task_name = t_name
    actor = (x_admin_actor or "").strip() or None
    _record_pipeline_task(
        task_id=new_task.id,
        task_name=task_name,
        task_type=task_record["task_type"],
        params=params,
        requested_by=actor,
        request_ip=_resolve_request_ip(http_request, x_forwarded_for),
        user_agent=(user_agent or "").strip() or None,
    )
    note = f"[retry] new_task_id={new_task.id} by={actor or 'unknown'} ip={_resolve_request_ip(http_request, x_forwarded_for) or 'unknown'}"
    _append_pipeline_task_note(task_id, note)
    return {
        "task_id": new_task.id,
        "status": "queued",
        "retried_from": task_id,
        "params": params,
    }


@app.get("/api/v1/pipeline/tasks")
def list_pipeline_tasks(
    task_type: str = Query(default="backfill"),
    limit: int = Query(default=10, ge=1, le=100),
    x_admin_token: Optional[str] = Header(default=None),
):
    _require_admin_token(x_admin_token)
    return {
        "items": _list_recent_pipeline_tasks(task_type=task_type, limit=limit)
    }


@app.get("/api/v1/pipeline/groups")
def list_pipeline_groups(
    limit: int = Query(default=20, ge=1, le=100),
    x_admin_token: Optional[str] = Header(default=None),
):
    _require_admin_token(x_admin_token)
    connection = get_db_connection()
    try:
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        # Define 'interesting' business task names that should be treated as root groups in the UI
        # even if they are technically children of the scheduler task.
        business_tasks = (
            'pipeline.tasks.crawl.run_all_spiders_automatic',
            'pipeline.tasks.translate.auto_translate_articles',
            'pipeline.tasks.embed.auto_embed_articles',
            'pipeline.tasks.crawl.manual_ingest_from_spiders',
            'pipeline.tasks.backfill.manual_global_processing',
            'pipeline.tasks.backfill.run_domestic_metadata_backfill',
            'pipeline.tasks.backfill.manual_generate_embeddings'
        )
        
        # Tasks that are internal implementation details and should never be top-level roots
        internal_tasks = (
            'pipeline.tasks.translate.translate_next_pending_article',
            'pipeline.tasks.embed.embed_next_pending_article',
            'pipeline.tasks.crawl.run_priority_spiders',
            'pipeline.tasks.crawl.run_spider'
        )

        cursor.execute(
            """
            WITH RECURSIVE task_tree AS (
                -- Fetch potential roots: business tasks, or non-scheduler tasks, 
                -- OR scheduler tasks that actually have children (did something).
                SELECT task_id, task_name, task_type, state, params, result, error_message,
                       requested_by, created_at, updated_at, parent_task_id,
                       (task_name = ANY(%s) AND parent_task_id IS NOT NULL) as is_business_child
                FROM pipeline_task_runs pr
                WHERE 
                    -- 1. It's a business root we specifically want
                    task_name = ANY(%s)
                    -- 2. OR it's a root task that is NOT the frequent scheduler AND NOT an internal child task
                    OR (parent_task_id IS NULL 
                        AND task_name <> 'pipeline.tasks.orchestrate.dispatch_periodic_tasks'
                        AND task_name <> ALL(%s)
                    )
                    -- 3. OR it's a scheduler task that actually produced children
                    OR (task_name = 'pipeline.tasks.orchestrate.dispatch_periodic_tasks' AND EXISTS (
                        SELECT 1 FROM pipeline_task_runs child WHERE child.parent_task_id = pr.task_id
                    ))
                ORDER BY created_at DESC
                LIMIT 100
            ),
            descendants AS (
                SELECT * FROM task_tree
                
                UNION ALL
                
                SELECT c.task_id, c.task_name, c.task_type, c.state, c.params, c.result, c.error_message,
                       c.requested_by, c.created_at, c.updated_at, c.parent_task_id,
                       false as is_business_child
                FROM pipeline_task_runs c
                INNER JOIN descendants p ON c.parent_task_id = p.task_id
                WHERE c.task_name <> ALL(%s)
            )
            SELECT DISTINCT ON (task_id) * FROM descendants ORDER BY task_id, created_at DESC
            LIMIT 200
            """,
            (list(business_tasks), list(business_tasks), list(internal_tasks), list(business_tasks))
        )
        tasks = cursor.fetchall()

        # ── Reconcile stale states ──────────────────────────────
        # SKIPPED: This loop iterates through Celery states which can hang the API if Redis/Celery is slow.
        pass

        # Ensure we don't return too many to the frontend, but enough for grouping
        # Also, make sure manual_ingest tasks are grouped under a friendly name in the UI if needed
        # but for now, they are already in business_tasks, just need to make sure the results are sorted.
        tasks.sort(key=lambda x: x['created_at'], reverse=True)
        return {"items": tasks[:200]}
    finally:
        connection.close()


@app.get("/api/v1/pipeline/spiders")
def list_available_spiders(x_admin_token: Optional[str] = Header(default=None)):
    _require_admin_token(x_admin_token)
    from pipeline.tasks.crawl import get_all_spiders
    return {"spiders": get_all_spiders()}


@app.get("/api/v1/pipeline/runtime")
def pipeline_runtime(x_admin_token: Optional[str] = Header(default=None)):
    _require_admin_token(x_admin_token)
    return get_pipeline_runtime_status()


@app.get("/api/v1/pipeline/schedules")
def get_periodic_schedules(x_admin_token: Optional[str] = Header(default=None)):
    _require_admin_token(x_admin_token)
    connection = get_db_connection()
    try:
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT id, name, task_path, cron_expr, params, is_enabled, last_run_at FROM pipeline_periodic_tasks ORDER BY id ASC")
        return {"items": cursor.fetchall()}
    finally:
        connection.close()


class ScheduleToggleRequest(BaseModel):
    is_enabled: bool

@app.post("/api/v1/pipeline/schedules/{schedule_id}/toggle")
def toggle_periodic_schedule(schedule_id: int, req: ScheduleToggleRequest, x_admin_token: Optional[str] = Header(default=None)):
    _require_admin_token(x_admin_token)
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("UPDATE pipeline_periodic_tasks SET is_enabled = %s WHERE id = %s", (req.is_enabled, schedule_id))
        connection.commit()
        return {"status": "success", "is_enabled": req.is_enabled}
    finally:
        connection.close()


class ScheduleUpdateRequest(BaseModel):
    cron_expr: str

@app.post("/api/v1/pipeline/schedules/{schedule_id}/update")
def update_periodic_schedule(schedule_id: int, req: ScheduleUpdateRequest, x_admin_token: Optional[str] = Header(default=None)):
    _require_admin_token(x_admin_token)
    
    # 使用croniter进行完整的cron表达式验证
    try:
        from croniter import croniter
        from datetime import datetime
        import pytz
        
        # 验证cron表达式
        tz = pytz.timezone('Asia/Shanghai')
        base_time = tz.localize(datetime.now())
        
        # 尝试创建croniter对象，如果表达式无效会抛出异常
        cron = croniter(req.cron_expr, base_time)
        
        # 可选：计算下一个执行时间用于预览
        next_time = cron.get_next(datetime)
        
    except ImportError:
        # 如果croniter未安装，使用基本验证
        logger.warning("croniter库未安装，使用基本cron表达式验证")
        parts = req.cron_expr.split()
        if len(parts) != 5:
            raise HTTPException(
                status_code=400, 
                detail="Invalid cron expression. Must have exactly 5 parts (minute hour day month weekday)."
            )
    except Exception as e:
        # 使用具体的异常类型而不是字符串匹配
        from croniter import (
            CroniterError,
            CroniterBadCronError,
            CroniterBadDateError,
            CroniterNotAlphaError,
            CroniterUnsupportedSyntaxError,
        )
        
        error_msg = str(e)
        
        # 根据具体的异常类型提供错误信息
        if isinstance(e, CroniterBadDateError):
            detail = f"Invalid cron expression: invalid date. {error_msg}"
        elif isinstance(e, CroniterNotAlphaError):
            detail = f"Invalid cron expression: syntax error (non-numeric character). {error_msg}"
        elif isinstance(e, CroniterUnsupportedSyntaxError):
            detail = f"Invalid cron expression: unsupported syntax. {error_msg}"
        elif isinstance(e, CroniterBadCronError):
            # CroniterBadCronError 包含多种错误：范围错误、语法错误等
            if "out of range" in error_msg:
                detail = f"Invalid cron expression: value out of range. {error_msg}"
            elif "invalid range" in error_msg or "must not be zero" in error_msg:
                detail = f"Invalid cron expression: invalid value. {error_msg}"
            elif "Exactly 5, 6 or 7 columns" in error_msg:
                detail = "Invalid cron expression: must have exactly 5 parts (minute hour day month weekday)."
            else:
                detail = f"Invalid cron expression: syntax error. {error_msg}"
        elif isinstance(e, CroniterError):
            detail = f"Invalid cron expression: {error_msg}"
        else:
            detail = f"Invalid cron expression: {error_msg}"
        
        raise HTTPException(status_code=400, detail=detail)
    
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("UPDATE pipeline_periodic_tasks SET cron_expr = %s WHERE id = %s", (req.cron_expr, schedule_id))
        connection.commit()
        
        # 返回更多信息
        response = {
            "status": "success", 
            "cron_expr": req.cron_expr,
            "message": "Schedule updated successfully"
        }
        
        # 如果croniter可用，添加下一个执行时间预览
        try:
            from croniter import croniter
            tz = pytz.timezone('Asia/Shanghai')
            base_time = tz.localize(datetime.now())
            cron = croniter(req.cron_expr, base_time)
            next_time = cron.get_next(datetime)
            response["next_execution"] = next_time.strftime('%Y-%m-%d %H:%M')
        except:
            pass
            
        return response
    finally:
        connection.close()
