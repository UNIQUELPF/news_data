import json
import os
from typing import Any

import httpx

from pipeline.rollout import ROLLOUT_PROFILES
from pipeline.search_config import get_search_runtime_status


class LLMClientError(RuntimeError):
    pass


def _strip_trailing_slash(value: str) -> str:
    return value[:-1] if value.endswith("/") else value


def is_llm_enabled() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


def get_embedding_provider() -> str:
    return os.getenv("EMBEDDING_PROVIDER", "openai").strip().lower()


def get_translation_model() -> str:
    return os.getenv("TRANSLATION_MODEL", "gpt-4.1-mini")


def get_translation_mode() -> str:
    return "llm" if is_llm_enabled() else "placeholder"


def get_embedding_model() -> str:
    provider = get_embedding_provider()
    if provider == "demo":
        return os.getenv("DEMO_EMBEDDING_MODEL", "demo-semantic-v1")
    if provider == "local":
        return os.getenv("LOCAL_EMBEDDING_MODEL", "BAAI/bge-m3")
    return os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")


def is_embedding_enabled() -> bool:
    provider = get_embedding_provider()
    if provider == "demo":
        return True
    if provider == "local":
        return True
    return is_llm_enabled()


def get_llm_base_url() -> str:
    return _strip_trailing_slash(os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"))


def get_translation_runtime_status() -> dict[str, Any]:
    enabled = is_llm_enabled()
    return {
        "mode": get_translation_mode(),
        "enabled": enabled,
        "model": get_translation_model(),
        "base_url": get_llm_base_url() if enabled else None,
        "production_ready": enabled,
    }


def get_embedding_runtime_status() -> dict[str, Any]:
    provider = get_embedding_provider()
    enabled = is_embedding_enabled()
    status: dict[str, Any] = {
        "provider": provider,
        "enabled": enabled,
        "model": get_embedding_model(),
        "production_ready": False,
    }
    if provider == "openai":
        status["base_url"] = get_llm_base_url() if is_llm_enabled() else None
        status["production_ready"] = bool(enabled and os.getenv("OPENAI_API_KEY"))
        return status
    if provider == "local":
        status["device"] = _get_local_embedding_device()
        status["batch_size"] = _get_local_embedding_batch_size()
        status["production_ready"] = bool(
            os.getenv("LOCAL_EMBEDDING_MODEL")
            and os.getenv("LOCAL_EMBEDDING_DEVICE")
            and os.getenv("LOCAL_EMBEDDING_BATCH_SIZE")
        )
        return status
    if provider == "demo":
        status["production_ready"] = False
        return status
    return status


def get_pipeline_runtime_status() -> dict[str, Any]:
    translation = get_translation_runtime_status()
    embedding = get_embedding_runtime_status()
    warnings: list[str] = []

    if translation["mode"] != "llm":
        warnings.append("Translation is running in placeholder mode")
    if embedding["provider"] == "demo":
        warnings.append("Embedding is running in demo mode")
    if embedding["provider"] == "openai" and not embedding["production_ready"]:
        warnings.append("OpenAI embedding provider is configured without a usable API key")
    if embedding["provider"] == "local" and not embedding["production_ready"]:
        warnings.append("Local embedding provider is missing model or device configuration")

    return {
        "translation": translation,
        "embedding": embedding,
        "search": get_search_runtime_status(),
        "recommended_rollout": {
            stage: {
                "translate_limit": profile["translate_limit"],
                "embed_limit": profile["embed_limit"],
                "description": profile["description"],
            }
            for stage, profile in ROLLOUT_PROFILES.items()
        },
        "production_ready": translation["production_ready"] and embedding["production_ready"],
        "warnings": warnings,
    }


def _get_headers() -> dict[str, str]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise LLMClientError("OPENAI_API_KEY is not configured")
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def _extract_json_payload(text: str) -> dict[str, Any]:
    text = text.strip()
    if not text:
        raise LLMClientError("empty translation response")

    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3:
            text = "\n".join(lines[1:-1]).strip()

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise LLMClientError("translation response is not valid JSON")
    return json.loads(text[start : end + 1])


def _chat_completion_json(*, system_prompt: str, user_prompt: str) -> dict[str, Any]:
    payload = {
        "model": get_translation_model(),
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }

    with httpx.Client(timeout=120.0) as client:
        response = client.post(
            f"{get_llm_base_url()}/chat/completions",
            headers=_get_headers(),
            json=payload,
        )
        response.raise_for_status()

    data = response.json()
    message = data["choices"][0]["message"]["content"]
    return _extract_json_payload(message)


def translate_article_content(
    *,
    title: str | None,
    content: str | None,
    source_language: str | None,
    target_language: str = "zh-CN",
) -> dict[str, str | None]:
    parsed = _chat_completion_json(
        system_prompt=(
            "You are a professional Intelligence Analyst and Translator. "
            "Your goal is to process business and policy news with extreme precision. "
            "The accuracy of structured data (category and companies) is as important as the translation quality.\n\n"
            "TASK 1: TRANSLATION\n"
            "- Translate into professional, concise Simplified Chinese.\n"
            "- Ensure the summary (2-4 sentences) captures the core impact of the news.\n\n"
            "TASK 2: CATEGORY CLASSIFICATION\n"
            "- YOU MUST choose one from: [政治, 经济, 军事, 法规, 科技, 社会, 环境, 其他].\n"
            "- Mapping: Finance/Trade/Markets/Industry -> 经济; Compliance/Law/Regulation -> 法规; "
            "AI/Chips/Software/Space -> 科技; ASEAN/Energy/Climate -> 环境.\n\n"
            "TASK 3: ENTITY EXTRACTION (STRICTLY CORPORATE)\n"
            "- Scan BOTH the TITLE and CONTENT for all involved companies or corporate entities.\n"
            "- DO NOT extract government departments, non-profit organizations, or macro-political groups (e.g., G20, ASEAN).\n"
            "- List them in 'involved_companies' as a comma-separated string.\n"
            "- For globally known giants, USE Chinese names: e.g., Google->谷歌, Intel->英特尔, NVIDIA->英伟达, "
            "Meta->Meta, Apple->苹果公司, Tesla->特斯拉, Microsoft->微软, Amazon->亚马逊, OpenAI->OpenAI.\n"
            "- DO NOT miss entities that appear in the title. If no companies are found, return empty string.\n\n"
            "Return strict JSON format with the following exact keys:\n"
            "- title_translated: translated title in Simplified Chinese\n"
            "- summary_translated: 2-4 sentence summary in Simplified Chinese capturing the core impact\n"
            "- content_translated: translated full content in Simplified Chinese\n"
            "- category: one of the specified categories from the list above\n"
            "- involved_companies: comma-separated string of company names (or empty string if none found)"
        ),
        user_prompt=(
            f"Source language: {source_language or 'unknown'}\n"
            f"Target language: {target_language}\n\n"
            "Please translate the title and full content, generate a 2-4 sentence Chinese summary, "
            "classify the news category, and extract involved companies/organizations.\n\n"
            f"Title:\n{title or ''}\n\n"
            f"Content:\n{content or ''}"
        ),
    )
    return {
        "title_translated": parsed.get("title_translated"),
        "summary_translated": parsed.get("summary_translated"),
        "content_translated": parsed.get("content_translated"),
        "category": parsed.get("category"),
        "involved_companies": parsed.get("involved_companies"),
    }


def extract_domestic_article_metadata(
    *,
    title: str | None,
    content: str | None,
) -> dict[str, Any]:
    parsed = _chat_completion_json(
        system_prompt=(
            "You extract structured metadata from mainland China policy and business news articles. "
            "Do not rewrite the article. Focus on factual extraction only.\n\n"
            "Return strict JSON with these keys:\n"
            "- category: one of [政治, 经济, 军事, 法规, 科技, 社会, 环境, 其他]\n"
            "- province: mainland China province-level region short name, such as 北京, 广东, 江苏. "
            "Use empty string if unclear.\n"
            "- city: mainland China city short name, such as 北京, 深圳, 苏州. "
            "Use empty string if unclear.\n"
            "- involved_companies: comma-separated company or market entity names only. "
            "Do not include government bodies or associations unless they are the main economic actor. "
            "Use empty string if none.\n"
            "- confidence: number from 0 to 1.\n"
            "If the article mentions multiple places, choose the primary place most directly tied to the event."
        ),
        user_prompt=(
            "Extract metadata for this Chinese domestic article.\n\n"
            f"Title:\n{title or ''}\n\n"
            f"Content:\n{content or ''}"
        ),
    )
    return {
        "category": parsed.get("category"),
        "province": parsed.get("province"),
        "city": parsed.get("city"),
        "involved_companies": parsed.get("involved_companies"),
        "confidence": parsed.get("confidence"),
    }


_LOCAL_EMBEDDING_MODEL = None


def _get_local_embedding_device() -> str:
    return os.getenv("LOCAL_EMBEDDING_DEVICE", "cpu")


def _get_local_embedding_batch_size() -> int:
    return int(os.getenv("LOCAL_EMBEDDING_BATCH_SIZE", "16"))


def _get_local_embedding_model():
    global _LOCAL_EMBEDDING_MODEL

    if _LOCAL_EMBEDDING_MODEL is not None:
        return _LOCAL_EMBEDDING_MODEL

    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise LLMClientError(
            "sentence-transformers is not installed; local embedding provider is unavailable"
        ) from exc

    _LOCAL_EMBEDDING_MODEL = SentenceTransformer(
        get_embedding_model(),
        device=_get_local_embedding_device(),
        trust_remote_code=True,
    )
    return _LOCAL_EMBEDDING_MODEL


def _embed_texts_local(texts: list[str]) -> tuple[list[list[float]], str]:
    model = _get_local_embedding_model()
    vectors = model.encode(
        texts,
        batch_size=_get_local_embedding_batch_size(),
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    return vectors.tolist(), get_embedding_model()


def _embed_texts_demo(texts: list[str]) -> tuple[list[list[float]], str]:
    def embed_one(text: str) -> list[float]:
        lowered = (text or "").lower()
        ai_score = 0.0
        eu_score = 0.0
        energy_score = 0.0
        geo_score = 0.0

        ai_keywords = ["ai", "openai", "人工智能", "模型", "治理", "合规", "compliance", "frontier"]
        eu_keywords = ["eu", "europe", "欧盟", "德国", "法案", "责任", "罚款", "regulation"]
        energy_keywords = ["能源", "东盟", "asean", "transition", "grid", "lng", "financing", "电网"]
        geo_keywords = ["政治", "经济", "policy", "economy", "企业", "监管", "summit", "峰会"]

        for keyword in ai_keywords:
            if keyword in lowered:
                ai_score += 1.0
        for keyword in eu_keywords:
            if keyword in lowered:
                eu_score += 1.0
        for keyword in energy_keywords:
            if keyword in lowered:
                energy_score += 1.0
        for keyword in geo_keywords:
            if keyword in lowered:
                geo_score += 1.0

        base = [ai_score, eu_score, energy_score, geo_score]
        norm = sum(value * value for value in base) ** 0.5
        if norm == 0:
            return [0.5, 0.5, 0.5, 0.5]
        return [value / norm for value in base]

    return [embed_one(text) for text in texts], get_embedding_model()


def _embed_texts_openai(texts: list[str]) -> tuple[list[list[float]], str]:
    if not texts:
        return [], get_embedding_model()

    payload = {
        "model": get_embedding_model(),
        "input": texts,
    }
    with httpx.Client(timeout=120.0) as client:
        response = client.post(
            f"{get_llm_base_url()}/embeddings",
            headers=_get_headers(),
            json=payload,
        )
        response.raise_for_status()

    data = response.json()
    embeddings = [item["embedding"] for item in data["data"]]
    return embeddings, payload["model"]


def embed_texts(texts: list[str]) -> tuple[list[list[float]], str]:
    provider = get_embedding_provider()
    if provider == "demo":
        return _embed_texts_demo(texts)
    if provider == "local":
        return _embed_texts_local(texts)
    return _embed_texts_openai(texts)
