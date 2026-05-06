---
name: verify_spider_quality
description: Use when verifying spider output quality — checking date-based pagination stop correctness (timezone/panic-break/zone-crossing issues) or content/image extraction accuracy against original pages. Triggers on "verify spider quality", "test spider quality", "检查爬虫质量", "验证爬虫质量", "content drift check", "date stop check".
---

# Spider Quality Verification

## Overview

Two-phase quality check for V2 SmartSpider instances. Phase 1 validates that date-based pagination stops correctly. Phase 2 compares `auto_parse_item` output against original page extraction to catch content drift or image loss.

Runs per-spider or per-directory. Incremental by default — only spiders that fail a phase get re-tested unless `--full` is requested.

## Architecture

```
verify_spider_quality
    ├── Phase 1: Date Stop Audit ── run WITHOUT item limit, verify spider stops by date window
    └── Phase 2: Content Diff    ── fetch 1 article, compare V2 vs ground-truth
```

---

## Phase 1: Date Stop Audit

### Goal

Confirm the spider stops pagination BECAUSE dates fell outside the window, NOT because of misconfiguration. Detect false-positive panic breaks.

### Step 1.1: Run Spider (NO forced item limit)

The spider must stop **by itself** when dates fall outside the configured window. A 120s timeout is the safety net — if the spider is still running at 120s, the date breaker is broken.

**Incremental mode** (uses DB window, fast for spiders with history):
```bash
timeout 120 docker-compose exec -T crawl-worker bash -c \
  "cd news_scraper_project && scrapy crawl <spider_name> -a full_scan=False" \
  2>&1 | tee /tmp/spider_test.log
```

**Full scan mode** (uses `default_start_date` from settings, for first-time crawls):
```bash
timeout 120 docker-compose exec -T crawl-worker bash -c \
  "cd news_scraper_project && scrapy crawl <spider_name> -a full_scan=True" \
  2>&1 | tee /tmp/spider_test.log
```

Default to `full_scan=False`. Use `full_scan=True` only if the spider has no DB history.

### Step 1.2: Extract Key Signals from Logs

| Signal | grep pattern | What it tells us |
|--------|-------------|-----------------|
| Finish reason | `'finish_reason': '[^']+'` | **Must be `finished`** — natural exhaustion, not forced close |
| Items scraped | `'item_scraped_count': \d+` | How many articles found before the window closed |
| Window info | `INCREMENTAL MODE\|FULL SCAN\|cutoff\|Latest DB` | What date boundary the spider is using |
| Too-old filter | `Filtered out \(too old\)` | Article older than `earliest_date` floor |
| Below-cutoff filter | `Filtered out \(below cutoff\)` | Article before the sliding window — **proof the date breaker triggered** |
| No-date filter | `Filtered out \(no date\)` | `strict_date_required=True` blocked an article — is this correct? |
| Panic break | `STRICT STOP` | Spider killed itself because a listing block had no date |
| Hanging pagination | `page=` or `?page=` in crawled URLs | Count distinct page numbers to see how far it went |
| Timeout | `timeout` exit code 124 | Spider did not stop within 120s — **date breaker broken** |
| ERROR lines | ` ERROR ` | Any crash or exception |

### Step 1.3: Diagnosis Rules

**✅ Date stop working correctly** — ALL of:
- `finish_reason = finished` (spider stopped naturally, not killed by us)
- Spider completed within 120s
- At least one of: `Filtered out (too old)` OR `Filtered out (below cutoff)` OR `item_scraped_count > 0` with reasonable page count (< 30 pages for full_scan)
- No `STRICT STOP` false positives
- No `Filtered out (no date)` on every single article

**❌ Date breaker NOT working** — ANY of:
- Timeout (124): spider ran > 120s without stopping → `has_valid_item_in_window` never went False
- `finish_reason = shutdown` or `unknown`: spider crashed or was killed
- Pages crawled > 50 without any `Filtered out` signals → blind pagination
- `Filtered out (no date)` on 100% of articles → date extraction broken on listing page

**⚠ Special cases** (WARN, not FAIL):
- `finish_reason = finished`, 0 items, 0 `Filtered out` — spider completed instantly (API returned nothing, or DB window covers everything). Manually verify.
- 1-2 `Filtered out (no date)` among many good articles — some article blocks lack dates, not a breaker issue.

**False-positive panic break** — `STRICT STOP` fired but:
- The listing page HAS article blocks
- Some blocks have dates, others don't
- → **Fix:** only `return` if ALL blocks on the page lack dates, not just one

**Timezone off-by-one** — spider stops at wrong boundary:
- Items near UTC day boundary (00:00/23:59) consistently filtered wrong
- → **Fix:** verify `source_timezone` matches the site's declared timezone

**Blind pagination** — spider keeps going past the window:
- Many pages crawled, `Filtered out` on every article but `has_valid_item_in_window` stays True
- → **Fix:** `has_valid_item_in_window = True` must be AFTER `should_process()` check

### Step 1.4: Output

| Spider | Time | Items | Pages | TooOld | Below | NoDate | Panic | Finish | Verdict |
|--------|------|-------|-------|--------|-------|--------|-------|--------|---------|
| es_abc | 12s | 23 | 2 | 45 | 0 | 0 | 0 | finished | **PASS** |
| xx_hang | 120s | — | 80 | 0 | 0 | 0 | 0 | timeout | **FAIL** |
| yy_api | 3s | 0 | 1 | 0 | 0 | 0 | 0 | finished | WARN |

---

## Phase 2: Content & Image Diff

### Goal

Compare what `auto_parse_item` returns against a direct page extraction (ground truth). Catch `fallback_content_selector` misconfig, missing og:image fallback, empty titles.

### Step 2.1: Fetch One Article

Use the spider to scrape exactly 1 article:

```bash
docker-compose exec -T crawl-worker bash -c \
  "cd news_scraper_project && scrapy crawl <spider_name> -a full_scan=True -s CLOSESPIDER_ITEMCOUNT=1" \
  2>&1 | tee /tmp/spider_1item.log
```

Extract the article URL from the log (e.g., from `'url': 'https://...'`).

### Step 2.2: Extract Ground Truth

Fetch the article page directly and extract content with broad selectors (NOT `auto_parse_item`):

```bash
# Get the raw page
curl -sL -H "User-Agent: Mozilla/5.0 ..." "$ARTICLE_URL" > /tmp/article.html

# Ground-truth content: all <p> inside any article-like container
python3 -c "
from bs4 import BeautifulSoup
soup = BeautifulSoup(open('/tmp/article.html'), 'html.parser')
# Remove noise
for t in soup(['script','style','nav','footer','aside','button']):
    t.decompose()
# Broad extraction
containers = soup.select('article, main, [role=main], .content, .post, .entry')
if not containers:
    containers = [soup]
paras = []
for c in containers:
    for p in c.find_all(['p','h2','h3','h4','li']):
        txt = p.get_text().strip()
        if len(txt) > 20:
            paras.append(txt)
print('GROUND_TRUTH_LEN:', len('\n\n'.join(paras)))
print('GROUND_TRUTH_PARAS:', len(paras))

# Ground-truth images
imgs = set()
for c in containers:
    for img in c.find_all('img'):
        src = img.get('src') or img.get('data-src') or ''
        if src and not src.endswith(('.svg','.gif')):
            imgs.add(src)
# Also check og:image
og = soup.find('meta', property='og:image')
if og:
    imgs.add(og.get('content',''))
print('GROUND_TRUTH_IMAGES:', len(imgs))
"
```

### Step 2.3: Extract V2 Output

From the spider run in Step 2.1, capture what `auto_parse_item` returned:

```bash
grep -oP '"content_plain":\s*".*?"' /tmp/spider_1item.log | head -1
grep -oP '"title":\s*".*?"' /tmp/spider_1item.log | head -1  
grep -oP '"images":\s*\[.*?\]' /tmp/spider_1item.log | head -1
```

Or more reliably, add a custom pipeline step that dumps the first item to a JSON file.

### Step 2.4: Compare

| Metric | V2 | Ground Truth | Ratio | Threshold |
|--------|-----|-------------|-------|-----------|
| Content length (chars) | `v2_len` | `gt_len` | `v2/gt` | > 0.4 |
| Word count | `v2_wc` | `gt_wc` | `v2/gt` | > 0.4 |
| Image count | `v2_imgs` | `gt_imgs` | | >= 1 if gt_imgs >= 1 |
| Title length | `v2_title` | — | | > 5 chars |
| Publish time | `v2_pt` | — | | not None |

**Verdict:**
- **PASS** — content ratio > 0.6, images >= 1 (if page has images), title > 5 chars
- **WARN** — content ratio 0.4-0.6, or images = 0 but page has images
- **FAIL** — content ratio < 0.4, or title empty, or publish_time None

### Step 2.5: Output

| Spider | V2 Len | GT Len | Ratio | V2 Imgs | GT Imgs | Title OK | PT OK | Verdict |
|--------|--------|--------|-------|---------|---------|----------|-------|---------|
| es_abc | 2340 | 3120 | 0.75 | 2 | 3 | PASS | PASS | PASS |
| xx_bad | 120 | 4500 | 0.03 | 0 | 4 | PASS | PASS | **FAIL** |

---

## Incremental Mode (Default)

Unless `--full` is requested, test only spiders that changed since last verification:

```bash
# Check which spider files changed since last verify run
git diff --name-only HEAD -- 'news_scraper_project/news_scraper/spiders/*/'
```

If no git history available, test all.

---

## Quick Reference

| Want to test | Command / Action |
|-------------|-----------------|
| Single spider | `verify_spider_quality es_abc` |
| All spiders in a country | `verify_spider_quality spain/` |
| All 11 countries | `verify_spider_quality all` |
| Phase 1 only | `verify_spider_quality --phase1 es_abc` |
| Phase 2 only | `verify_spider_quality --phase2 es_abc` |
| Full mode (ignore git) | `verify_spider_quality --full all` |

## Common Mistakes

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `Filtered out (no date)` on every article | `strict_date_required=True` but listing page has no dates | Set `strict_date_required=False` and extract dates on detail pages only |
| Panic break after 1 page | One article block has no date but others do | Don't `return` on first block — only panic if ALL blocks on page lack dates |
| Content ratio < 0.2 | `fallback_content_selector` wrong or ContentEngine missed body | Check the article HTML manually, update `fallback_content_selector` to the actual content container |
| 0 images when page has hero image | og:image fallback not triggered | Verify `auto_parse_item` image fallback logic runs correctly |
| Spider stops after page 1 with 0 items | `earliest_date` too recent (DB has latest record close to now) | Run with `-a full_scan=True` for first crawl, or set `start_date` earlier |
| Timezone causes boundary misses | `source_timezone` wrong for the site | Check the site's declared timezone (usually in `<meta>` or footer), not the country's default |
| Spider immediately exits with 0 requests | `async def start()` missing `dont_filter=True` — initial request filtered as duplicate | Add `dont_filter=True` to the first Request in `async def start()` |
| Timeout: spider keeps paginating forever | Listing page has no dates, `has_valid_item_in_window` always True | Use `_stop_pagination` pattern: call `should_process(url, pub_time)` in `parse_detail`, check `self._stop_pagination` at top of `parse_list`, and still call `should_process(url)` on listing page for dedup |
| Timeout: filtering active but spider still slow | Listing-no-date + `CONCURRENT_REQUESTS > 1` — 20 detail requests queued before `_stop_pagination` can stop them | Set `CONCURRENT_REQUESTS_PER_DOMAIN: 1` so detail pages process serially. First old article sets `_stop_pagination`, queue drains quickly instead of piling up across pages |