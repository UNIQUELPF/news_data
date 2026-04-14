# Search Tuning

这份文档只记录当前版本最小可执行的搜索调优基线，不讨论复杂 rerank。

## 当前权重

默认 hybrid 权重由环境变量控制：

```bash
HYBRID_KEYWORD_WEIGHT=0.35
HYBRID_SEMANTIC_WEIGHT=0.65
```

后端会自动归一化，前端搜索面板和 `/api/v1/pipeline/runtime` 都会显示当前生效值。

## 推荐调参顺序

1. 先固定真实 translation / embedding provider。
2. 再选一组查询样例，人工检查 Top 5 结果。
3. 只调 hybrid 权重，不要同时改太多变量。
4. 每次调参至少比较 `keyword` / `semantic` / `hybrid` 三种模式。

## 基线查询样例

建议优先用这几类样例做人工评估：

- `OpenAI 欧盟合规`
  - 目标：欧盟 AI 法规、OpenAI 欧洲合规、德国/EU 监管应优先
- `东盟 能源 转型 融资`
  - 目标：ASEAN、能源转型、融资政策类文章应优先
- `美联储 利率 通胀`
  - 目标：Fed、美国宏观政策、利率表态优先
- `德国 人工智能 法案`
  - 目标：德国、欧盟、AI 责任/法规类结果优先
- `金砖 支付 体系`
  - 目标：BRICS、跨境支付、结算体系相关文章优先

## 调参建议

- 如果关键词非常明确，但语义结果总把“相关但不精确”的文章顶上来：
  - 提高 `HYBRID_KEYWORD_WEIGHT`
- 如果跨语言查询很多，而关键词匹配过窄：
  - 提高 `HYBRID_SEMANTIC_WEIGHT`
- 如果筛选条件很多，比如国家/组织/时间窗口已经很窄：
  - 先保持当前权重，重点看召回是否足够

## 当前目标

第一阶段不追求最优，只追求：

- Top 3 不离题
- 过滤条件下结果稳定
- 相似文章不会明显跑偏

满足这三点后，再考虑更复杂的 rerank 或 query rewrite。
