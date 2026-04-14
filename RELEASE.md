# Release

这份文档定义当前仓库的最小发版约定，重点覆盖：

- Git tag 规则
- Docker 镜像 tag 规则
- 一次最小 release 的顺序

## 1. 版本规则

建议使用 `vX.Y.Z` 形式的 tag，例如：

```bash
v0.1.0
v0.1.1
v0.2.0
```

约定：

- `vX.Y.Z`：正式发布版本
- `X`：不兼容变更
- `Y`：功能增量
- `Z`：修复或小型工程改动

## 2. 镜像命名

当前 release workflow 产出两类镜像：

- `ghcr.io/<owner>/news-data-api`
- `ghcr.io/<owner>/news-data-frontend`

其中 `<owner>` 来自 GitHub 仓库 owner。

## 3. 镜像 Tag 规则

[release-images.yml](/home/fanhe/NingTai/news_data/.github/workflows/release-images.yml) 当前会生成这些 tag：

- `ref branch`：分支名
  - 例如 `main`
- `ref tag`：Git tag
  - 例如 `v0.1.0`
- `sha`：提交 SHA
  - 例如 `sha-abc1234`
- `latest`
  - 仅默认分支启用

建议理解为：

- 日常回归：看 `sha-*`
- 测试环境：可跟 `main`
- 正式发布：跟 `vX.Y.Z`
- 人工默认入口：`latest`

## 4. Release Workflow

当前 workflow 支持两种触发方式：

1. 推送 `v*` tag
2. 手动 `workflow_dispatch`

行为：

- tag push：自动构建并推送 API / Frontend 镜像
- workflow_dispatch：默认只构建不推送
- workflow_dispatch + `push_images=true`：构建并推送

## 5. 最小发版顺序

推荐顺序：

1. 先确认 CI 通过
2. 本地执行环境预检
3. 本地执行总检查
4. 打 release tag
5. 推送 tag
6. 等待 `Release Images` 完成
7. 在目标环境更新镜像 tag

建议命令：

```bash
zsh scripts/pre_release_check.sh .env http://127.0.0.1:8000 http://127.0.0.1:18080
git tag v0.1.0
git push origin v0.1.0
```

## 6. 目标环境更新建议

部署时建议固定使用版本 tag，而不是长期只跟 `latest`：

```yaml
image: ghcr.io/<owner>/news-data-api:v0.1.0
image: ghcr.io/<owner>/news-data-frontend:v0.1.0
```

这样回滚会简单很多。

## 7. 回滚建议

如果新版本异常，优先回滚到上一版已知可用 tag：

```yaml
image: ghcr.io/<owner>/news-data-api:v0.0.9
image: ghcr.io/<owner>/news-data-frontend:v0.0.9
```

再重新执行最小 smoke 验证。
