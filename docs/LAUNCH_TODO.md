# Launch TODO

这份文档只记录“从当前可演示状态到稳定可上线状态”还没收口的事项。

## P0 阻塞项

- `Reuters` 站点专项处理
  - 当前对应 spider: [usa/reuters_spider.py](/home/fanhe/NingTai/news_data/news_scraper_project/news_scraper/spiders/usa/reuters_spider.py)
  - 已验证普通请求、`curl_cffi`、Playwright 路径都会收到 `401`
  - 需要二选一：
    - 找 Reuters 的可用弱入口：sitemap / RSS / archive / topic feed
    - 引入代理 / 持久化浏览器上下文 / 特殊请求策略

- 真实翻译生产配置收口
  - 生产回填 runbook 和验收脚本已补齐
  - 还需要校验 `translation-worker` 的限流、失败重试、成本控制
  - 还需要明确哪些字段全量翻译，哪些字段按需翻译

- 真实 embedding 生产配置收口
  - 生产回填 runbook 和验收脚本已补齐
  - 还需要明确最终 provider：`openai` / `local`
  - 还需要跑一轮历史文章向量回填并验证真实效果

- 搜索质量调优
  - 搜索验收 runbook 和检查脚本已补齐
  - 还需要调整 `keyword / semantic / hybrid` 权重
  - 还需要校验多语种查询、按国家/组织/企业过滤下的召回表现
  - 还需要确认“相似文章”在真实数据上的稳定性

## P1 高优先级

- 完整流水线运维入口收口
  - `POST /api/v1/pipeline/run` 和 `scripts/run_pipeline.sh` 已可用
  - 还需要决定是否把 `pipeline_run` 直接接进 React 管理面板，而不是仅保留 API / shell 入口
  - 需要明确默认 spider 批次、运行窗口和失败告警策略

- 前端正式版继续打磨
  - 静态 HTML 原型已移除
  - 当前生产入口已经收口到 Next.js 版本
  - 后续重点是继续补交互和监控视图，而不是维护双轨

- 爬虫运行监控
  - 增加每个 spider 的成功率、最近抓取量、失败原因分布
  - 增加 worker 队列长度、回填延迟、翻译失败率、embedding 失败率

- 管理面板增强
  - 最近任务列表的持久化筛选和搜索
  - 失败任务详情页
  - 基础审计查询视图

- 重点站点抽样验收继续推进
  - 当前已实跑：
    - `malaysia_enanyang`
    - `malaysia_sinchew`
    - `malaysia_malaymail`
    - `malaysia_theedge`
    - `malaysia_malaysiakini`
    - `argentina_ambito`
    - `egypt_mubasher`
    - `usa_arstechnica`
    - `usa_forbes`
    - `usa_reuters`
  - 仍需继续抽样其它高价值国家和来源

## P2 可延期

- 更细粒度的权限模型
  - 当前只有 `ADMIN_API_TOKEN`
  - 还没有用户体系和角色权限

- 更完整的任务治理
  - 死信处理
  - 自动重试策略
  - 任务优先级和并发配额

- 语义检索的进一步增强
  - 查询改写
  - rerank
  - 更复杂的 hybrid 排序

- 更完整的前端工程化质量门
  - 更多 hook / 组件测试
  - 端到端 smoke

## 站点状态

- 已验证正常：
  - [malaysia/enanyang_spider.py](/home/fanhe/NingTai/news_data/news_scraper_project/news_scraper/spiders/malaysia/enanyang_spider.py)
  - [malaysia/sinchew_spider.py](/home/fanhe/NingTai/news_data/news_scraper_project/news_scraper/spiders/malaysia/sinchew_spider.py)
  - [malaysia/malaymail_spider.py](/home/fanhe/NingTai/news_data/news_scraper_project/news_scraper/spiders/malaysia/malaymail_spider.py)
  - [malaysia/theedge_spider.py](/home/fanhe/NingTai/news_data/news_scraper_project/news_scraper/spiders/malaysia/theedge_spider.py)
  - [malaysia/malaysiakini_spider.py](/home/fanhe/NingTai/news_data/news_scraper_project/news_scraper/spiders/malaysia/malaysiakini_spider.py)
  - [argentina/argentina_ambito.py](/home/fanhe/NingTai/news_data/news_scraper_project/news_scraper/spiders/argentina/argentina_ambito.py)
  - [brics/egypt/egypt_mubasher.py](/home/fanhe/NingTai/news_data/news_scraper_project/news_scraper/spiders/brics/egypt/egypt_mubasher.py)
  - [usa/arstechnica_spider.py](/home/fanhe/NingTai/news_data/news_scraper_project/news_scraper/spiders/usa/arstechnica_spider.py)

- 部分受限但可运行：
  - [usa/forbes_spider.py](/home/fanhe/NingTai/news_data/news_scraper_project/news_scraper/spiders/usa/forbes_spider.py)
    - 首页 HTML 可抓
    - `simple-data` API 被 `403`，当前已跳过

- 明确失败：
  - [usa/reuters_spider.py](/home/fanhe/NingTai/news_data/news_scraper_project/news_scraper/spiders/usa/reuters_spider.py)
    - 普通请求 / `curl_cffi` / Playwright 都被 `401`

## 当前建议顺序

1. 跑真实翻译与真实 embedding 的 `small rollout`。
2. 用真实数据执行搜索验收并调第一轮权重。
3. 继续完善 Next.js 前端的运维与检索体验。
4. 补基础监控与告警。
5. 攻克 `Reuters` 或确认替代来源。
