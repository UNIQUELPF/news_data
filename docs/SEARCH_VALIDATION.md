# Search Validation

这份文档只覆盖“生产回填之后，如何验证搜索是否已经达到第一阶段可用水位”。

## 目标

验证三种搜索模式都已经具备基本可用性：

- `keyword`
- `semantic`
- `hybrid`

第一阶段不追求最优，只要求：

- 每个基线查询三种模式都有结果
- Top 3 不明显离题
- `hybrid` 结果不比 `keyword` 和 `semantic` 更差

## 0. 前置条件

先确认生产回填已经至少跑过 `small`：

- [PRODUCTION_ROLLOUT.md](/home/fanhe/NingTai/news_data/PRODUCTION_ROLLOUT.md)

并确认：

- `/api/v1/pipeline/runtime` 显示 `production_ready = true`
- `/api/v1/pipeline/summary` 里 `translation_completed` 和 `embedding_completed` 已经增加

## 1. 固定样例查询

当前项目固定使用这组查询做第一轮验收：

- `OpenAI 欧盟合规`
- `东盟 能源 转型 融资`
- `美联储 利率 通胀`
- `德国 人工智能 法案`
- `金砖 支付 体系`

## 2. 自动检查脚本

执行：

```bash
zsh scripts/check_search_quality.sh .env http://127.0.0.1:8000
```

脚本会对每个查询依次检查：

- `keyword`
- `semantic`
- `hybrid`

并输出每种模式的：

- 命中数量
- Top 3 标题

任何一个查询在任何一个模式下如果返回空结果，脚本会直接失败。

## 3. 人工验收重点

脚本通过之后，仍建议人工看一轮前端：

- 打开首页
- 用相同查询切换 `关键词 / 语义 / 混合`
- 重点看 Top 3 标题是否明显离题

建议重点关注：

- `OpenAI 欧盟合规`
  - 欧盟 AI 监管、OpenAI 欧洲合规类结果应靠前
- `东盟 能源 转型 融资`
  - ASEAN、能源转型、融资政策类结果应靠前
- `美联储 利率 通胀`
  - Fed、利率表态、宏观政策类结果应靠前

## 4. 什么时候需要调权重

如果出现这些现象，再回头调：

- `semantic` 相关，但 `hybrid` 明显被弱关键词结果压住
  - 降低 `HYBRID_KEYWORD_WEIGHT`
- 查询很精确，但 `hybrid` 总把泛相关内容顶上来
  - 提高 `HYBRID_KEYWORD_WEIGHT`

当前权重配置位置：

- `.env`
- `/api/v1/pipeline/runtime`
- 搜索面板顶部的 hybrid 权重展示

## 5. 第一阶段通过标准

满足下面三条，就可以认为“搜索已达到第一阶段可用水位”：

- 自动检查脚本通过
- 人工抽查 Top 3 基本不离题
- 切换 `keyword / semantic / hybrid` 时没有明显坏掉的模式
