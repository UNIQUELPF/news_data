import os


def _parse_weight(name: str, default: float) -> float:
    raw_value = os.getenv(name, str(default)).strip()
    try:
        value = float(raw_value)
    except ValueError:
        return default
    return max(0.0, value)


def get_hybrid_ranking_weights() -> dict[str, float]:
    keyword_weight = _parse_weight("HYBRID_KEYWORD_WEIGHT", 0.35)
    semantic_weight = _parse_weight("HYBRID_SEMANTIC_WEIGHT", 0.65)

    total = keyword_weight + semantic_weight
    if total <= 0:
        keyword_weight = 0.35
        semantic_weight = 0.65
        total = 1.0

    return {
        "keyword": keyword_weight / total,
        "semantic": semantic_weight / total,
    }


def get_search_runtime_status() -> dict:
    return {
        "hybrid_weights": get_hybrid_ranking_weights()
    }
