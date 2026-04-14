ROLLOUT_PROFILES = {
    "small": {
        "translate_limit": 25,
        "embed_limit": 25,
        "description": "最小验证批次，适合首次联通生产 provider",
    },
    "medium": {
        "translate_limit": 100,
        "embed_limit": 100,
        "description": "中等批次，适合校验质量和稳定性",
    },
    "large": {
        "translate_limit": 300,
        "embed_limit": 300,
        "description": "较大批次，适合生产回填扩容阶段",
    },
}


def resolve_rollout_profile(stage: str | None) -> dict:
    normalized = (stage or "small").strip().lower()
    return ROLLOUT_PROFILES.get(normalized, ROLLOUT_PROFILES["small"]) | {"stage": normalized if normalized in ROLLOUT_PROFILES else "small"}
