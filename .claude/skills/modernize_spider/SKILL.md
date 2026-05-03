---
name: modernize_spider
description: Use when migrating an old Scrapy spider to the V2 SmartSpider architecture. Covers class definition, listing page with date-based circuit breaker, detail page extraction via auto_parse_item, and test verification.
---

# V2 Spider Modernization

## When to Use

Trigger when the user asks to:
- "Modernize" or "refactor" or "upgrade" a spider to V2
- Migrate a legacy `BaseNewsSpider` spider to `SmartSpider`
- Implement a new spider following current conventions

Reference implementation: `news_scraper_project/news_scraper/spiders/albania/albania.py`

## Prerequisites (Read Before Editing)

1. Read the target spider's current code completely.
2. Read `news_scraper/spiders/smart_spider.py` to understand available built-in methods.
3. Identify: is this a standard HTML listing page, or an API-driven spider?

## Step 1: Class Foundation

Replace the old base class and add required metadata:

```python
from news_scraper.spiders.smart_spider import SmartSpider

class MySpider(SmartSpider):
    name = 'my_spider'
    source_timezone = 'Region/City'     # pytz timezone
    country_code = 'XXX'                # 3-letter ISO
    country = '中文名'                   # Chinese display name
    language = 'xx'                     # 2-letter language code
    use_curl_cffi = True
    allowed_domains = ['example.com']

    custom_settings = {
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "AUTOTHROTTLE_ENABLED": True,
    }
```

**Rules:**
- Always set `use_curl_cffi = True` unless the site actively breaks with it.
- `source_timezone` must be a valid pytz timezone string.
- `CONCURRENT_REQUESTS` ≤ 2 and `DOWNLOAD_DELAY` ≥ 1.0 for standard HTML sites. API-based spiders can tune higher.

## Step 2: Entry Point

Two patterns are valid. Pick based on the site:

**Pattern A: `start_requests`** — Use for simple cases where URL generation is straightforward:
```python
def start_requests(self):
    yield scrapy.Request(url, callback=self.parse_list, meta={'page': 1})
```

**Pattern B: `async def start`** — Use when the spider name needs to match `allowed_domains` for middleware or you want the cleaner `dont_filter` semantics:
```python
async def start(self):
    yield scrapy.Request(url, callback=self.parse, dont_filter=True)
```

Both patterns work. Reference spiders use both. Choose the one that fits.

## Step 3: Listing Page with Circuit Breaker

This is the most critical part. The listing page must:
1. Extract `publish_time` from each list item
2. Call `self.should_process(url, publish_time)` for incremental filtering
3. Track `has_valid_item_in_window` for pagination control
4. NEVER hardcode a page limit

### Standard HTML listing pattern:

```python
def parse(self, response):
    articles = response.css('SELECTOR_FOR_EACH_ITEM')
    self.logger.info(f"Found {len(articles)} articles on {response.url}")

    has_valid_item_in_window = False

    for article in articles:
        # Extract URL and date using the ORIGINAL spider's proven selectors
        url = response.urljoin(article.css('a.title::attr(href)').get())
        date_str = article.css('time.date::text').get()

        # Parse date for circuit breaker
        dt_local = dateparser.parse(date_str.strip() if date_str else '')
        publish_time = self.parse_to_utc(dt_local) if dt_local else None

        # SmartSpider incremental gate
        if not self.should_process(url, publish_time):
            continue

        has_valid_item_in_window = True
        yield scrapy.Request(
            url,
            callback=self.parse_detail,
            dont_filter=self.full_scan,
            meta={'publish_time_hint': publish_time}
        )

    # Pagination: ONLY driven by circuit breaker + next link existence
    if has_valid_item_in_window:
        next_page = response.css('a.next::attr(href)').get()
        if next_page:
            yield response.follow(next_page, callback=self.parse, dont_filter=True)
```

### Date extraction rules:
- **⛔ Always extract dates from the list page HTML, never from URL patterns**: Many sites mix URL formats — some articles have `/post/2026/05/03/title`, others use `/post/clean-slug`. URL-based date extraction breaks the circuit breaker whenever a clean-slug article appears. Extract from the list page HTML (e.g. `.date a::text`, `time::attr(datetime)`) where every item consistently has a date element.
- **⛔ Iterate structured list items, not loose link selectors**: Use `.category-page-post-item` or equivalent item containers. Do NOT use `a[href*="/post/"]` which grabs sidebar links too. Structured iteration lets you reliably extract both URL and date from each item.
- **XPath is case-sensitive**: Modern JS frameworks render `dateTime` (camelCase). Use defensive XPath: `//@dateTime | //@datetime`.
- **Respect original selectors**: If the old spider has validated XPath/CSS selectors or custom date parsing (e.g. `parse_az_date`), KEEP them. Only wrap them in the V2 pattern.
- **Avoid `dateparser` over-config**: Do NOT pass `languages` or `DATE_ORDER` unless the date format is genuinely ambiguous. These settings break ISO 8601 parsing (`2026-04-27` fails under `DMY`).
- **`should_process` gates**: The method checks (in order): earliest_date floor → full_scan bypass (returns True immediately, skipping strict_date_required) → strict_date_required (rejects None dates) → cutoff_date window → URL dedup. **Note**: with `full_scan=True`, articles with `publish_time=None` pass through because the bypass gate comes before strict_date_required.

### Circuit breaker rules (NON-NEGOTIABLE):
- When `publish_time` is `None`, `should_process` returns `False` (due to `strict_date_required=True` default). This automatically prevents `has_valid_item_in_window` from being set → pagination stops. Do NOT override this behavior.
- Never write `if page < N` or `if offset < N`. The ONLY termination conditions are: ① `has_valid_item_in_window == False`, or ② no "next page" link found.
- If you need a global safety net, use `CLOSESPIDER_ITEMCOUNT` in custom_settings.

## Step 4: Detail Page Extraction

The detail page should almost always delegate to `auto_parse_item()`:

```python
def parse_detail(self, response):
    item = self.auto_parse_item(
        response,
        title_xpath="//div[contains(@class,'article-header')]//h1/text()",
        publish_time_xpath="//div[contains(@class,'author-info')]//time/text()",
    )
    yield item
```

### What `auto_parse_item()` does automatically:
- Title: tries `title_hint` → explicit xpath → `og:title` → `<title>` tag
- Publish time: tries explicit xpath → `article:published_time` meta → `publish_time_hint` → ContentEngine fallback
- Content: delegates to `ContentEngine.process()` with `fallback_content_selector`
- **Images**: ContentEngine returns dicts `[{"url": "...", "alt": "..."}]`. `auto_parse_item()` normalizes them to a flat string array. It also falls back to `og:image` if ContentEngine found nothing, and deduplicates images already embedded in body text.
- Language, country_code, country, section: auto-filled from class attributes

**You do NOT need to manually handle og:image or image dedup** — the framework handles it.

### XPath rules for detail page:
- **Restrict XPath to a container**: Use `//div[contains(@class,'author')]//time` not `//time`. The latter scans the entire page and can match sidebars.
- **Exception**: `//meta[@property='...']` and `//meta[@name='...']` are safe to use globally since `<meta>` tags only appear in `<head>`.

### Fallback content selector:
Set `fallback_content_selector` on the class. It must target the article body — the div that contains the actual text and inline images:
```python
fallback_content_selector = ".entry-content .et_builder_inner_content"
```
Use the tightest selector that captures the article body. Avoid broad layout selectors like `.page-content .col-lg-8` which may pick up unrelated page elements on some articles.

**⛔ Verify the selector is unique on the detail page**: Some themes (e.g. Divi) reuse the same class name in Header, Content, and Footer. A bare `.et_builder_inner_content` will `select_one()` the first occurrence (Header), returning nothing useful. Always:
1. Download a detail page HTML with `curl_cffi`
2. `grep -n 'class="YOUR_SELECTOR"' debug_detail.html` to count how many times it appears
3. If > 1, prefix with a parent scope: `.entry-content .et_builder_inner_content`

**Featured photo outside content area**: Some sites place the header image in a separate div (e.g. `.featured-photo`) that sits outside the article body. If your `fallback_content_selector` excludes it, manually extract and prepend it in `parse_detail`:
```python
featured_img = response.css('.featured-photo img::attr(src)').get()
if featured_img:
    featured_url = response.urljoin(featured_img)
    images = item.get('images') or []
    if featured_url not in images:
        images.insert(0, featured_url)
    item['images'] = images
```

### Manual item assembly (API spiders only):
For API-driven spiders (like `uae_wam.py`), skip `auto_parse_item()` and assemble the item manually:
```python
def parse_api_detail(self, response):
    data = json.loads(response.text)
    mock_response = HtmlResponse(url=response.url, body=data.get("body", ""), encoding='utf-8')
    content_data = self.extract_content(mock_response)

    item = {
        "url": article_url,
        "title": data.get("title"),
        "publish_time": response.meta.get('publish_time'),
        "language": self.language,
        "country": self.country,
        "country_code": self.country_code,
        **content_data,  # includes images, content_markdown, content_cleaned, content_plain
    }
    yield item
```
When assembling manually, ensure `content_data` comes LAST so its null fields don't overwrite your extracted metadata.

## Step 5: Verify Before Claiming Done

Run a test crawl:
```bash
docker-compose exec crawl-worker bash -c \
  "cd news_scraper_project && scrapy crawl <name> -a full_scan=True -s CLOSESPIDER_ITEMCOUNT=5"
```

Check the output for:
1. **Dates**: Are `publish_time` values correct and non-null?
2. **Images**: Does each item have a non-empty `images` array with absolute URLs?
3. **Markdown**: Is `content_markdown` non-empty, with images inline, and free of sidebar noise?
4. **Pagination stop**: Does the spider stop on its own (not via CLOSESPIDER_ITEMCOUNT)?
5. **No hardcoded limits**: Grep for `page <` and `offset <` — must return nothing.

## Batch Workflow (Multiple Spiders)

When migrating multiple spiders in a directory:
1. Migrate ONE spider at a time.
2. Test-crawl that spider immediately.
3. Report the result before starting the next.
4. Never modify multiple spiders in one pass — an error in one would require reverting all.
