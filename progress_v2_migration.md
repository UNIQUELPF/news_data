# SmartSpider V2 迁移进度

## 总览

| 状态 | 数量 | 说明 |
|------|------|------|
| ✅ 正常工作 | 25 | 代码正确，测试通过 |
| ✅ 已修复 | 3 | jp_kyodo、informkz、kapital（本轮修复） |
| ❌ 网络问题 | 2 | jp_bloomberg（PerimeterX）、iq_elaph/iq_moj（Cloudflare） |

早前已修复：jiji、reuters_jp、zakon、ge_bpn、hr_index

---

## 日本 (japan)

| 爬虫 | 状态 | 备注 |
|------|------|------|
| bloomberg | ❌ | PerimeterX 403 拦截，非代码问题 |
| jiji | ✅ | 已修复：publish_time_xpath 使用了错误的 `article:published_time` → `itemprop="datePublished"` |
| kyodo | ✅ | 已修复：`item.get('content')` → `item.get('content_plain')` |
| meti | ✅ | |
| reuters_jp | ✅ | 已修复：`item.get('content')` → `item.get('content_plain')` |

## 哈萨克斯坦 (kazakhstan)

| 爬虫 | 状态 | 备注 |
|------|------|------|
| digitalbusiness | ✅ | |
| inbusiness | ✅ | |
| informburo | ✅ | |
| informkz | ✅ | 已修复：站点 CSS 改版，`.catpageCard` → `a.news-card` |
| kapital | ✅ | 已修复：放弃 Next.js 改为标准 HTML，全量重写 |
| lsm | ✅ | |
| zakon | ✅ | 已修复：`playwright_include_page` 异步生成器在 `page.close()` 后继续 yield 导致生命周期冲突，改为在滚动循环内 yield |

## 黎巴嫩 (lebanon)

| 爬虫 | 状态 | 备注 |
|------|------|------|
| elnashra | ✅ | |
| lebanon24 | ✅ | |
| lpgov | ✅ | 代码正确，测试环境 cutoff 被已有数据推到未来，用 `full_scan=1` 验证 |
| nna | ✅ | |

## 卢森堡 (luxembourg)

| 爬虫 | 状态 | 备注 |
|------|------|------|
| delano | ✅ | |
| gouvernement | ✅ | |
| lequotidien | ✅ | |
| paperjam | ✅ | |
| wort | ✅ | |

## 马来西亚 (malaysia)

| 爬虫 | 状态 | 备注 |
|------|------|------|
| enanyang | ✅ | |
| malaymail | ✅ | |
| malaysiakini | ✅ | |
| orientaldaily | ✅ | |
| sinchew | ✅ | |

## 其他已测试

| 爬虫 | 国家 | 状态 | 备注 |
|------|------|------|------|
| ge_bpn | 格鲁吉亚 | ✅ | 已修复：移除 `wait_for_selector(".article_body_wrapper")`，部分页面无此元素导致超时 |
| hr_index | 克罗地亚 | ✅ | 已修复：pagination 的 `wait_for_selector` 加 5s timeout |
| gr_kathimerini | 希腊 | ✅ | |
| gr_minfin | 希腊 | ✅ | |
| gr_naftemporiki | 希腊 | ✅ | |
| gr_tovima | 希腊 | ✅ | |
| iq_elaph | 伊拉克 | ❌ | Cloudflare 403，非代码问题 |
| iq_moj | 伊拉克 | ❌ | 网络不可达，非代码问题 |
| it_borse | 意大利 | ✅ | |
| it_ilsole24ore | 意大利 | ✅ | |
| it_mef | 意大利 | ✅ | |
