import scrapy
from bs4 import BeautifulSoup
from datetime import datetime
from news_scraper.spiders.smart_spider import SmartSpider


class UzAnhorSpider(SmartSpider):
    name = "uz_anhor"
    source_timezone = "Asia/Tashkent"

    country_code = "UZB"
    country = "乌兹别克斯坦"
    language = "ru"

    allowed_domains = ["anhor.uz"]

    # 经济新闻类别列表
    base_url = "https://anhor.uz/category/economy/page/{}/"

    custom_settings = {
        "USER_AGENT": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "CONCURRENT_REQUESTS": 16,
        "DOWNLOAD_DELAY": 0.5,
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_TIMEOUT": 30,
    }

    use_curl_cffi = True
    fallback_content_selector = ".article__content, #article-content"
    strict_date_required = True

    async def start(self):
        """Initial requests entry point."""
        yield scrapy.Request(
            self.base_url.format(1), callback=self.parse, dont_filter=True
        )

    def parse(self, response):
        # 根据探测，文章块通常在 posts-list 的子容器中
        # 每个块包含标题 posts-list__head 和日期 posts-list__date
        article_blocks = response.css(".posts-list .row > div, .posts-list__item")

        current_page = response.meta.get("page", 1)
        has_valid_item_in_window = False

        for block in article_blocks:
            link = block.css("h3.posts-list__head a::attr(href)").get()
            date_str = block.css("span.posts-list__date::text").get()

            if not link:
                # 尝试更深一层的查找
                link = block.css("a.posts-list__head-link::attr(href)").get()

            if not link:
                continue

            # 日期转换 (DD.MM.YYYY) -> UTC
            pub_time = None
            if date_str:
                try:
                    dt_obj = datetime.strptime(date_str.strip(), "%d.%m.%Y")
                    pub_time = self.parse_to_utc(dt_obj)
                except Exception:
                    pass

            # Panic Break: 有链接但无日期，说明页面结构变化，终止翻页
            if pub_time is None:
                self.logger.error(
                    f"STRICT STOP: No date found for {link}. Terminating spider."
                )
                return

            if not self.should_process(link, pub_time):
                continue

            has_valid_item_in_window = True
            yield response.follow(
                link,
                self.parse_detail,
                meta={"publish_time_hint": pub_time},
            )

        # 如果主选择器没抓到任何有效项，尝试兼容其他布局 (置顶大图等)
        if not has_valid_item_in_window:
            for link in response.css(
                "h2 a::attr(href), .entry-title a::attr(href)"
            ).getall():
                if "/news/" in link:
                    has_valid_item_in_window = True
                    yield response.follow(link, self.parse_detail)

        # 翻页逻辑: 只要当前窗口内有有效数据，继续翻页
        if has_valid_item_in_window:
            next_page = current_page + 1
            yield scrapy.Request(
                self.base_url.format(next_page),
                callback=self.parse,
                meta={"page": next_page},
            )

    def _extract_content(self, response):
        """Extract article content via BS4 when ContentEngine returns nothing.

        The article page is WordPress-based with content in div.article__content.
        The .entry-content class (WordPress default) is not used by this theme.
        """
        soup = BeautifulSoup(response.text, 'html.parser')
        root_el = (soup.select_one('.article__content')
                   or soup.select_one('#article-content')
                   or soup.select_one('.article__body'))
        if not root_el:
            self.logger.warning("Could not find article content container")
            return ''
        for t in root_el(['script', 'style', 'nav', 'footer', 'aside', 'button', 'form']):
            t.decompose()
        parts = []
        for node in root_el.find_all(['p', 'h2', 'h3', 'li', 'blockquote']):
            text = node.get_text(strip=True)
            if text and len(text) > 10:
                parts.append(text)
        extracted = '\n\n'.join(parts)
        self.logger.info(f"BS4 extracted {len(extracted)} chars from article__content")
        return extracted

    def parse_detail(self, response):
        """Parse article detail page using SmartSpider auto extraction."""
        item = self.auto_parse_item(
            response,
            title_xpath="//h1/text() | //*[contains(@class, 'entry-title')]/text()",
        )

        # If ContentEngine returned empty or negligible content, use BS4 extraction
        if not item.get('content_plain') or len(item['content_plain']) < 50:
            content = self._extract_content(response)
            if content:
                item['content_plain'] = content
                item['content_cleaned'] = f'<div>{content}</div>'
                item['content_markdown'] = content
                self.logger.info(f"Overrode empty ContentEngine result with BS4 extraction ({len(content)} chars)")

        item["author"] = "Anhor.uz Economy"
        item["section"] = "Economy"

        yield item
