PIPELINE_SPIDER_PRESETS = [
    {
        "id": "malaysia_sample",
        "label": "马来西亚样例",
        "spiders": ["malaysia_enanyang", "malaysia_malaymail", "malaysia_theedge"],
    },
    {
        "id": "usa_sample",
        "label": "美国样例",
        "spiders": ["usa_arstechnica", "usa_forbes", "usa_cnbc"],
    },
    {
        "id": "high_priority",
        "label": "高优先级",
        "spiders": ["usa_fed", "usa_cnbc", "india_economic_times", "india_moneycontrol"],
    },
    {
        "id": "demo_mix",
        "label": "演示混合",
        "spiders": ["malaysia_enanyang", "argentina_ambito", "egypt_mubasher", "usa_arstechnica"],
    },
]
