# Skill: News Spider V2 Modernization

## Description
This skill is used to refactor legacy news scraping spiders into the modernized SmartSpider V2 architecture. It automates the migration from old-style Scrapy spiders to a unified, intelligent, and incremental framework.

## Goal
To ensure all news spiders follow the standardized V2 architecture, including proper UTC time handling, TLS impersonation (curl-cffi), and automatic content extraction while preserving existing validated selectors.

## Instructions

### 1. Class Foundation
- **Inherit**: `news_scraper.spiders.smart_spider.SmartSpider`.
- **Metadata**: Define the following class attributes:
  - `source_timezone`: (e.g., 'Europe/Sarajevo')
  - `country_code`: 3-letter ISO code.
  - `country`: Chinese name of the country.
  - `language`: 2-letter language code.
- **TLS Protection**: Always set `use_curl_cffi = True`.

### 2. Request Handling
- **Async Start**: Use `async def start(self)` instead of `start_urls`.
  ```python
  async def start(self):
      yield scrapy.Request(url, callback=self.parse, dont_filter=True)
  ```
- **Custom Settings**: Standardize to include (unless site needs specific tuning):
  ```python
  custom_settings = {
      "CONCURRENT_REQUESTS": 2, 
      "DOWNLOAD_DELAY": 1.0,
      "AUTOTHROTTLE_ENABLED": True,
  }
  ```

### 3. Efficient Research Rules
- **CURL First**: Always use `curl` (with `-H "User-Agent: ..."` and `-L`) to inspect HTML. Do NOT waste time with browser subagents unless strictly necessary for JS-heavy sites.
- **Human Intervention**: If `curl` returns empty/403 despite basic header spoofing, **STOP** and ask the USER for HTML source or manual inspection. Do not guess.
- **Preserve Existing Success**: If the original spider has accurate listing selectors, **DO NOT change them**. Only wrap them with the new date/panic logic.

### 4. Standard Verification Checklist (The 7-Points)
Before finishing a spider, verify these points and output them in the final report:
1.  **Listing Container**: Is the listing area precisely restricted (e.g. `.news-list`) to avoid sidebar noise?
2.  **Date Selector (Listing)**: Does it successfully extract dates for all listing items?
3.  **Date Order (DMY/MDY)**: Is `DATE_ORDER` correctly set for the target country (e.g. 'DMY' for Europe)?
4.  **Panic Break**: Does the spider use `return` (not `break`) to terminate the entire pagination chain on date failure?
5.  **Pagination Reliability**: Is `dont_filter=True` applied to the initial and all pagination requests?
6.  **Incremental Window**: Does the pagination correctly stop when hitting the historical floor?
7.  **Detail Selector**: Is the article body extraction precise and free of sidebar/footer clutter?

### 5. Listing Page Logic (Incremental)
- **Request Reliability**:
  - **Always set `dont_filter=True`** for the initial `start_urls` request and all subsequent pagination (`page=N`) requests. This ensures the spider always checks for new content even if the index URL was seen in a previous run.
- **Date Extraction Strategy**:
  - **Machine-Readable First**: If a `<time>` tag exists, prioritize the `datetime` attribute (ISO format) over visible text.
  - **XPath Case-Sensitivity Warning**: Modern JS frameworks (React/Next.js) often render standard HTML5 attributes in camelCase (e.g., `dateTime` instead of `datetime`). Scrapy's XPath via LXML is strictly case-sensitive. Always check raw `curl` HTML output and use defensive XPaths like `//@dateTime | //@datetime`.
  - **Preserve Existing Success**: If the original spider already has accurate listing selectors or link extraction logic, **DO NOT change them arbitrarily**. Only wrap them with the new date-parsing and "Panic Break" logic. Avoid re-debugging what was already working.
  - **Precise Listing Container**: Never search for `article` tags globally on a listing page. 
  - **Mandatory for Listing**: Date extraction on the listing page is **mandatory** to enable early-stopping. If missing, log a `self.logger.warning`.
- **Time Parsing**: 
  - **IMPORTANT**: If the existing spider has a working XPath/CSS selector or a custom parsing function (e.g., `parse_az_date`) for the publication date, **preserve it**.
  - **Dateparser ISO Conflict**: `dateparser` has a powerful internal auto-detect mechanism. Avoid explicitly passing `languages` or `settings={'DATE_ORDER': '...'}` unless strictly necessary for highly ambiguous formats. Forcing these settings will break standard ISO string parsing (e.g., `2026-04-27` fails under `DMY`).
  - Convert source-specific date strings to UTC using `self.parse_to_utc()`.
- **Filtering**: Use `if not self.should_process(url, publish_time): continue`.
- **Pagination Control**: 
  - **Incremental Safety**: Only proceed to the next page if `has_valid_item_in_window` is True.
  - **Panic Break (Strict Gate)**: If `publish_time` cannot be extracted on the listing page, use `break` to stop the loop and prevent pagination. This is a safety measure against accidental full-site backfills if selectors fail.
  - **Filtering**: Use `if not self.should_process(url, publish_time): continue`.
- **Metadata Passing**: Pass the parsed time as `publish_time_hint` in the request meta.
  ```python
  yield scrapy.Request(url, callback=self.parse_detail, meta={'publish_time_hint': publish_time})
  ```

### 6. Precise Content Extraction (Detail Page)
- **The "Surgical" Selector Strategy**:
  - **Avoid Fuzzy Selectors**: Do not use generic tags like `article` or `div.content` alone.
  - **The "Master Wrapper"**: Identify the **smallest unique container** that wraps the title, the featured image, and the body text (e.g., `.main-content.s-post-contain`).
  - **Single Selector Preference**: Set `fallback_content_selector` to this precise container. Avoid using comma-separated lists (OR logic) unless necessary for different page layouts, as it can lead to noisy extraction.
- **Featured Image Integrity**: 
  - Ensure the chosen selector covers the header/featured image area (often `.post-header`, `.featured-area`, or `.post-thumb`).
  - **og:image Priority**: Automated engines like Trafilatura easily mistake side-panel ads (e.g., "Dinheiro 3D") as the main image. Always explicitly extract `//meta[@property='og:image']/@content` and **prepend** it to the `item['images']` list so it is strictly treated as the primary image. Do not merely use it as a fallback.
  - **Frontend `[object Object]` Rendering Prevention**: Ensure that `item['images']` resolves to a list of plain strings (`['http...']`). If it's left as a dictionary (`[{'url': '...'}]`), it will render as `[object Object]` in the React frontend.
- **Clutter Cleaning**: 
  - Define `clutter_selectors` to remove "Read More", "Related Posts", and social share bars (e.g., `['.post-related', '.wa-post-read-next', 'aside']`).

### 7. Metadata & Detail Parsing
- **Fidelity**: Detail parsing must use `self.auto_parse_item(response)`.
- **Manual Overrides**: If `ContentEngine` misses metadata, manually set `item['author']`, `item['section']`, etc., in `parse_detail`.
- **UTC Enforcement**: All timestamps must be converted to UTC ISO format with the `Z` suffix.

### 8. Verification
- **Log Monitoring**: Verify that pagination stops correctly when reaching the date window.
- **Content Check**: Verify that `content_markdown` contains the main image and no sidebar clutter.
