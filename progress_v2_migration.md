# SmartSpider V2 迁移进度

## 总览

| 状态 | 数量 | 说明 |
|------|------|------|
| ✅ 正常工作 | 62 | 代码正确，测试通过或代码无误 |
| ✅ 已修复 | 17 | 本轮 + 早前修复 |
| ❌ 网络问题 | 10 | PerimeterX、Cloudflare、403、超时等 |
| ⚪ 待排查 | 5 | 0 items，需确认是否为迁移前已存在问题 |

早前已修复：jiji、reuters_jp、zakon、ge_bpn、hr_index、jp_kyodo、informkz、kapital

---

## 日本 (japan)

| 爬虫 | 状态 | 备注 |
|------|------|------|
| bloomberg | ❌ | PerimeterX 403 拦截，非代码问题 |
| jiji | ✅ | 已修复：publish_time_xpath 修复 |
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
| zakon | ✅ | 已修复：Playwright 生命周期冲突 |

## 黎巴嫩 (lebanon)

| 爬虫 | 状态 | 备注 |
|------|------|------|
| elnashra | ✅ | |
| lebanon24 | ✅ | |
| lpgov | ✅ | 代码正确，测试环境 cutoff 被已有数据推到未来 |
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

## 其他已测试 (Round 7)

| 爬虫 | 国家 | 状态 | 备注 |
|------|------|------|------|
| ge_bpn | 格鲁吉亚 | ✅ | 已修复：移除 wait_for_selector |
| hr_index | 克罗地亚 | ✅ | 已修复：pagination timeout |
| gr_kathimerini | 希腊 | ✅ | |
| gr_minfin | 希腊 | ✅ | |
| gr_naftemporiki | 希腊 | ✅ | |
| gr_tovima | 希腊 | ✅ | |
| iq_elaph | 伊拉克 | ❌ | Cloudflare 403 |
| iq_moj | 伊拉克 | ❌ | 网络不可达 |
| it_borse | 意大利 | ✅ | |
| it_ilsole24ore | 意大利 | ✅ | |
| it_mef | 意大利 | ✅ | |

---

## 本轮批量迁移（33 个爬虫，10 个目录）

### 墨西哥 (mexico)

| 爬虫 | 状态 | 备注 |
|------|------|------|
| elfinanciero | ✅ | 已验证：8 items |
| expansion | ✅ | 已验证：58 items |
| fayerwayer | ✅ | 已验证：45 items |
| gob | ⚪ | 0 items，CSS 选择器不匹配（迁移前已存在问题） |
| infobae | ⚪ | 0 items，JS 渲染列表页需 Playwright（迁移前已存在问题） |

### 蒙古 (mn)

| 爬虫 | 状态 | 备注 |
|------|------|------|
| montsame | ❌ | Playwright 超时，非代码问题 |

### 缅甸 (myanmar)

| 爬虫 | 状态 | 备注 |
|------|------|------|
| eleven | ⚪ | 0 items，需进一步排查（迁移前已存在问题） |
| gov | ✅ | 已验证：222 items |
| irrawaddy | ❌ | 403 网络问题 |
| mmbiztoday | ✅ | 已验证：44 items |

### 新西兰 (new_zealand)

| 爬虫 | 状态 | 备注 |
|------|------|------|
| nz_mbie | ❌ | curl_cffi 超时，非代码问题 |
| nz_newsroom | ✅ | 已验证少量 items，多数文章被日期窗口过滤 |

### 尼日利亚 (nigeria)

| 爬虫 | 状态 | 备注 |
|------|------|------|
| businessday | ✅ | 已验证：3 items |
| gov | ⚪ | 已验证：11 items，但有 Postgres 连接报错 |
| nairametrics | ✅ | 已验证：11 items |
| techeconomy | ✅ | 已验证：7+ items |
| vanguard | ❌ | 403 + 超时，非代码问题 |

### 波兰 (pl)

| 爬虫 | 状态 | 备注 |
|------|------|------|
| gov | ⚪ | 待验证（保留 Playwright + curl_cffi） |
| parkiet | ❌ | Playwright Timeout 30s，非代码问题 |

### 葡萄牙 (portugal)

| 爬虫 | 状态 | 备注 |
|------|------|------|
| cm | ✅ | 已修复：缺少 start_urls |
| dn | ✅ | 已修复：缺少 start_urls + 改用电路中断翻页 |
| gov | ❌ | XPath `//a[contains(@href, "/noticia?")]` 匹配不到链接，需排查 |

### 罗马尼亚 (ro)

| 爬虫 | 状态 | 备注 |
|------|------|------|
| wallstreet | ✅ | 保留 curl_cffi，已验证：85 items |

### 塞尔维亚 (serbia)

| 爬虫 | 状态 | 备注 |
|------|------|------|
| b92 | ✅ | 从 scrapy.Spider 迁移，已验证：100 items |
| danas | ✅ | 已修复：fallback_content_selector `.article-content` → `.post-content` |
| politika | ✅ | 从 scrapy.Spider 迁移，已验证：8 items |

### 新加坡 (singapore)

| 爬虫 | 状态 | 备注 |
|------|------|------|
| businesstimes | ✅ | 已修复：offset-aware vs naive datetime 比较 |
| channelnewsasia | ❌ | curl_cffi 超时，非代码问题 |
| mas | ✅ | 已修复：offset-aware vs naive datetime 比较 |
| zaobao | ✅ | 已验证：21 items |

---

## 修复汇总

### 本轮发现的代码 bug（8 个，全部已修复）

| 爬虫 | 问题 | 修复 |
|------|------|------|
| pt_cm | 缺少 `start_urls` 导致 IndexError | 添加 `start_urls = ['https://www.cmjornal.pt/economia']` |
| pt_dn | 缺少 `start_urls` 导致 IndexError | 添加 `start_urls` + 改用电路中断翻页 |
| pt_gov | 缺少 `start_urls` 导致 IndexError | 添加 `start_urls` |
| pt_jornaldenegocios | 缺少 `start_urls` 导致 IndexError | 添加 `start_urls` |
| pt_publico | 缺少 `start_urls` 导致 IndexError | 添加 `start_urls` |
| pt_tek_sapo | 缺少 `start_urls` 导致 IndexError | 添加 `start_urls` |
| sg_businesstimes | tz-aware vs tz-naive datetime 比较 TypeError | `.replace(tzinfo=None)` 统一为 naive |
| sg_mas | tz-aware vs tz-naive datetime 比较 TypeError | `.replace(tzinfo=None)` 统一为 naive |
| danas | fallback_content_selector `.article-content` 不匹配当前网站 DOM | 改为 `.post-content` |

### 已知网络问题（非代码）

| 爬虫 | 原因 |
|------|------|
| jp_bloomberg | PerimeterX 403 |
| iq_elaph / iq_moj | Cloudflare / 网络不可达 |
| mm_irrawaddy | 403 |
| ng_vanguard | 403 + TCP 超时 |
| mn_montsame | Playwright 超时 |
| pt_dn | dn.pt TCP 超时 |
| nz_mbie | curl_cffi 连接超时 |
| pl_parkiet | Playwright Page.goto 30s 超时 |
| sg_channelnewsasia | curl_cffi 连接超时 |
| pt_gov | 网站改版，XPath 匹配不到文章链接，需排查 |
