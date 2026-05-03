---
name: debug_spider
description: Use when a news spider malfunctions - not crawling new articles, over-crawling/endless pagination, missing images or body text, or returning 403 errors. Provides a standardized diagnostic and repair workflow.
---

# 爬虫排障 (Spider Debugging)

## When to Use

Trigger this skill when the user reports any of:
- Spider not picking up new articles
- Spider endlessly paginating (over-crawling)
- Detail pages missing images or body text
- All detail pages returning 403 (Cloudflare/anti-bot)
- Content markdown contains noisy sidebars, "related articles", or missing cover images

## Workflow: Diagnose Before Editing

### Step 0: Identify the failure mode

Read the spider code and recent logs. Classify the issue into one of the buckets below, then jump to the corresponding step. Do NOT edit code before knowing which bucket you're in.

| Symptom | Jump To |
|---------|---------|
| Not crawling new articles | Step 1: Date & should_process |
| Endless pagination | Step 2: Listing selector & circuit breaker |
| Missing images / body text | Step 3: Detail page extraction |
| All detail pages return 403 | Step 4: Anti-bot / Playwright |
| Markdown has noise / sidebar junk | Step 5: Content cleaning |

---

### Step 1: Date & `should_process` (Not Crawling New Articles)

1. **Check `source_timezone`**: Is it set correctly for the country?
2. **Check date extraction on listing page**: Does the spider actually extract `publish_time` from list items? If not, `should_process` will filter them out (due to `strict_date_required = True` by default in SmartSpider).
3. **Check HOW the date is extracted**: If the spider extracts dates from URL patterns (e.g. regex on `/post/DD/MM/YYYY-`), verify ALL article URLs follow that pattern. Many sites mix date-URLs and clean-URLs. Prefer extracting dates from the list page HTML (e.g. `.date a::text`), which is consistent across all items.
4. **Check `parse_date` / `dateparser` config**: If the spider sets custom `dateparser_settings`, verify they don't break ISO parsing. Avoid passing `languages` or `DATE_ORDER` unless the date format is truly non-standard.
5. **Try full_scan to isolate**: Run `scrapy crawl <name> -a full_scan=True -s CLOSESPIDER_ITEMCOUNT=5`. If this works but normal mode doesn't, the issue is in cutoff_date / dedup / window settings.
6. **⚠️ `full_scan=True` bypasses `strict_date_required`**: `should_process()` checks gates in order: earliest_date → full_scan (returns True immediately) → strict_date_required. So with `full_scan=True`, articles with `publish_time=None` WILL pass through. If you see "no date" filtering in normal mode but not full_scan, this is why.

---

### Step 2: Listing Selector & Circuit Breaker (Endless Pagination)

**Core principle**: The SmartSpider pagination circuit breaker relies on `has_valid_item_in_window`. If the listing selector is too broad (e.g. matching sidebar "popular articles"), dates will always be found and pagination never stops.

**Diagnostic actions:**

1. **Verify the selector scope**: Open the spider's `parse`/`parse_list` method. The loop that iterates articles — what CSS/XPath selects those items? If it's a bare `article`, `.post`, or `a[href*="/post/"]`, it may be over-matching.

2. **⚠️ Always iterate structured list items, not loose link selectors**:
   - ❌ `response.css('a[href*="/post/"]::attr(href)')` — grabs EVERY post link on the page, including sidebar "Related News" widgets.
   - ✅ `response.css('.category-page-post-item')` — iterates actual list item containers, scoped to the main content area.
   When the spider iterates structured items, you can reliably extract BOTH the URL and the date from each item's HTML.

3. **⚠️ Never rely solely on URL-based date extraction**: Many sites mix URL formats — some articles have dates in the URL (`/post/2026/05/03/title`), others use clean slugs (`/post/title`). This makes the circuit breaker unreliable because articles without URL dates get `publish_time=None`. Always prefer extracting dates from the list page HTML structure where every item consistently has a date element.

4. **Download real HTML via curl_cffi (the only reliable method)**:
   ```bash
   docker-compose exec crawl-worker bash -c \
     "python3 -c \"from curl_cffi import requests; r = requests.get('<LIST_URL>', impersonate='chrome110'); print(r.text)\" > /tmp/debug_list.html"
   docker-compose cp crawl-worker:/tmp/debug_list.html ./debug_list.html
   ```
   Never use browser DevTools to inspect HTML — the browser runs JavaScript that modifies the DOM, which the spider never sees.

5. **Analyze the HTML**:
   ```bash
   grep -oE 'class="[^"]+"' debug_list.html | sort | uniq -c | sort -nr | head -30
   grep -C 10 "target-class-name" debug_list.html | head -50
   ```

6. **Verify the selector matches ONLY main content**: Confirm selected container does NOT include sidebar "popular articles" or "latest news" widgets.

7. **Check the circuit breaker logic**: In the spider's parse loop, verify `has_valid_item_in_window` is only set to `True` when `should_process` returns `True` AND a valid date was extracted. If `publish_time` is `None`, the item MUST NOT set the flag (SmartSpider's `strict_date_required=True` enforces this by default).

8. **Check for hardcoded page limits**: Search for `if page < N` or `if offset < N` patterns. These mask selector problems and cause over-crawling when the selector is too broad.

---

### Step 3: Detail Page Extraction (Missing Images / Body Text)

1. **Check `fallback_content_selector`**: Does it target a single unique container that wraps title + featured image + body? Avoid comma-separated fallback lists; prefer one precise selector like `.main-content.s-post-contain`.

2. **Check og:image handling**: `auto_parse_item()` in SmartSpider already extracts `og:image` as a fallback when ContentEngine finds no images. If the spider manually builds items without calling `auto_parse_item()`, it must handle og:image itself.

3. **Check `images` field format**: `auto_parse_item()` normalizes all images to a flat string array `["http://..."]`. If the spider manually assembles the item dict, ensure images are NOT dicts `[{"url": "..."}]` — React will render `[object Object]`.

4. **Check ContentEngine fidelity**: When `fallback_content_selector` is set and the page has images, ContentEngine compares image counts between trafilatura output and the fallback area. If trafilatura stripped all images, it auto-switches to "Fidelity Mode" using BS4. Watch for `"Trafilatura stripped all images"` in logs.

---

### Step 4: Anti-bot / Playwright (403 on Detail Pages)

**Symptom**: List page returns 200 OK but detail pages all return 403.

1. **Verify with bare request**:
   ```bash
   docker-compose exec crawl-worker python -c "from curl_cffi import requests; print(requests.get('<DETAIL_URL>', impersonate='chrome110').status_code)"
   ```
   If this returns 403, curl_cffi alone is insufficient — the site requires JavaScript execution.

2. **Enable Playwright**: Set `playwright = True` on the spider class. Then ensure the `parse`/`parse_list` method passes `playwright: True` in request meta:
   ```python
   meta = {'publish_time_hint': publish_time}
   if getattr(self, 'playwright', False):
       meta['playwright'] = True
   yield scrapy.Request(url, callback=self.parse_detail, meta=meta)
   ```

3. **Test safely** without polluting production data:
   ```bash
   docker-compose exec crawl-worker bash -c \
     "cd news_scraper_project && scrapy crawl <spider_name> -a full_scan=True -s CLOSESPIDER_ITEMCOUNT=2"
   ```

---

### Step 5: Content Cleaning (Noise / Sidebar Junk)

1. **Add `clutter_selectors`** if the spider defines them — these are CSS selectors for elements that ContentEngine should strip before extraction.
2. **Check markdown output**: Temporarily add `self.logger.debug(f"Markdown: {item['content_markdown'][:300]}")` in `parse_detail` to inspect actual output.
3. **Common noise sources**: "Read more", "Related articles", social share bars, comment sections. If present in output, tighten `fallback_content_selector` to exclude footer/sidebar regions.

---

## Quick Diagnostic Commands

```bash
# Test crawl with item limit (safe, won't pollute production)
docker-compose exec crawl-worker bash -c \
  "cd news_scraper_project && scrapy crawl <name> -a full_scan=True -s CLOSESPIDER_ITEMCOUNT=3"

# Check what the spider actually receives (not browser DOM)
docker-compose exec crawl-worker bash -c \
  "python3 -c \"from curl_cffi import requests; r = requests.get('<URL>', impersonate='chrome110'); print(r.text[:5000])\""

# Clear Redis dedup filter if re-crawling needed
docker-compose exec redis redis-cli DEL "<spider_name>:dupefilter"
```

## Rules

- Never use browser DevTools to locate selectors. Always use curl_cffi in the container to get the actual HTML the spider receives.
- Never use `//div` or bare `//article` XPath — they scan the entire document and pick up sidebars.
- When a date parsing failure happens on a valid article block, the spider MUST break pagination (this is `strict_date_required`'s job).
- Fix one spider at a time. Verify with a test crawl before moving on.
