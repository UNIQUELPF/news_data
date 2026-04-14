# Production Rollout

这份文档只覆盖“真实翻译 + 真实 embedding”的分批回填，不覆盖爬虫策略本身。

## 目标

把系统从联调模式推进到生产模式，并且确保：

- `/api/v1/pipeline/runtime` 显示 `production_ready = true`
- 翻译不再走 `placeholder`
- embedding 不再走 `demo`
- 分批回填有明确的执行顺序和验收标准

## 0. 前置条件

先准备好 `.env`，至少确认：

```bash
OPENAI_API_KEY=...
OPENAI_BASE_URL=https://api.openai.com/v1
TRANSLATION_MODEL=gpt-4.1-mini

EMBEDDING_PROVIDER=local
LOCAL_EMBEDDING_MODEL=BAAI/bge-m3
LOCAL_EMBEDDING_DEVICE=cpu
LOCAL_EMBEDDING_BATCH_SIZE=16

ADMIN_API_TOKEN=...
PRODUCTION_PIPELINE_REQUIRED=1
```

如果你走远端 embedding，则改成：

```bash
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
```

## 1. 严格预检

```bash
PRODUCTION_PIPELINE_REQUIRED=1 zsh scripts/preflight.sh .env
```

预期：

- 通过时输出 `all checks passed`
- 若仍在 `placeholder` / `demo` 配置，会直接失败

## 2. 确认运行时状态

```bash
curl -H "X-Admin-Token: your-admin-token" \
  http://127.0.0.1:8000/api/v1/pipeline/runtime
```

重点确认：

- `production_ready = true`
- `translation.mode = "llm"`
- `embedding.provider != "demo"`
- `warnings` 为空，或者只剩可接受告警

管理面板顶部也会显示同样的 runtime 信息。

## 3. 按档位分批执行

项目已经预置三档 rollout：

- `small`
  - `translate_limit = 25`
  - `embed_limit = 25`
- `medium`
  - `translate_limit = 100`
  - `embed_limit = 100`
- `large`
  - `translate_limit = 300`
  - `embed_limit = 300`

执行方式：

```bash
ROLLOUT_STAGE=small zsh scripts/run_production_backfill.sh .env http://127.0.0.1:8000
ROLLOUT_STAGE=medium zsh scripts/run_production_backfill.sh .env http://127.0.0.1:8000
ROLLOUT_STAGE=large zsh scripts/run_production_backfill.sh .env http://127.0.0.1:8000
```

如果需要手动覆盖批量：

```bash
TRANSLATE_LIMIT=60 EMBED_LIMIT=60 zsh scripts/run_production_backfill.sh .env http://127.0.0.1:8000
```

## 4. 每一档的验收方式

执行回填后，先看运行时和统计：

```bash
zsh scripts/check_production_rollout.sh .env http://127.0.0.1:8000
```

这个脚本会检查：

- runtime 是否 `production_ready`
- `translation_failed` 是否超过阈值
- `embedding_failed` 是否超过阈值
- 当前任务排队、处理中、抓取运行状态

默认阈值：

- `MAX_TRANSLATION_FAILED=0`
- `MAX_EMBEDDING_FAILED=0`

如果允许小范围失败，可以放宽：

```bash
MAX_TRANSLATION_FAILED=2 MAX_EMBEDDING_FAILED=2 \
  zsh scripts/check_production_rollout.sh .env http://127.0.0.1:8000
```

## 5. 推荐执行顺序

### small

目的：

- 验证 provider 真连通
- 验证译文和向量能真实入库
- 验证搜索页面的 `semantic / hybrid` 有可用结果

通过标准：

- `production_ready = true`
- `translation_failed = 0`
- `embedding_failed = 0`
- 管理面板没有明显积压
- 随机抽查 3 到 5 篇文章，标题、摘要和语义结果合理

### medium

目的：

- 验证稳定性和吞吐
- 观察是否出现明显队列堆积

通过标准：

- `translation_processing` 和 `embedding_processing` 能持续下降
- `pending_tasks` 不长期堆积
- 失败摘要中没有系统性错误模式

### large

目的：

- 正式扩大量级
- 验证长时间运行下的健康度

通过标准：

- 失败率维持在可接受范围
- 面板里 `翻译失败 / 向量失败 / 失败 Spider Top` 没有持续恶化
- 搜索结果质量没有明显下降

## 6. 出现异常时看哪里

优先看管理面板：

- runtime 卡片
- 翻译/向量 pending、processing、failed
- 最近失败摘要
- Spider 健康度

也可以直接查接口：

```bash
curl -H "X-Admin-Token: your-admin-token" \
  http://127.0.0.1:8000/api/v1/pipeline/runtime

curl -H "X-Admin-Token: your-admin-token" \
  http://127.0.0.1:8000/api/v1/pipeline/summary

curl -H "X-Admin-Token: your-admin-token" \
  http://127.0.0.1:8000/api/v1/pipeline/monitor
```

如果是任务层面的问题，再看：

```bash
curl -H "X-Admin-Token: your-admin-token" \
  http://127.0.0.1:8000/api/v1/pipeline/tasks
```

## 7. 不建议的做法

- 不要在 `placeholder` / `demo` 模式下直接跑大批量回填
- 不要跳过 `small` 直接上 `large`
- 不要只看任务成功，不抽查搜索质量
