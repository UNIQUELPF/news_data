import re
from urllib.parse import urlparse


NON_ARTICLE_URL_RE = re.compile(
    r"("
    r"/(?:privacy|accessibil|contact|cookies?|terms|legal|mentions-legales|impressum|datenschutz)"
    r"|/(?:plan-du-site|sitemap|newsletter|login|signin|register|subscribe|account|author)"
    r"|/(?:category|categories|topics?|tag|tags|ranking|rankings)(?:/|$)"
    r"|/(?:podcast|podcasts|video|videos|events|careers|jobs|kids|education|learning)(?:/|$)"
    r"|/(?:about|a-propos|who-we-are|our-work|policies|council|statistics|data|gallery)(?:/|$)"
    r"|/(?:actualites|actualite|news|newsroom|press|releases?)/?$"
    r"|[?&]page=\d+|/page/\d+/?$"
    r"|/(?:20\d{2}|19\d{2})\.html$"
    r"|/(?:index|home)\.(?:html?|php)$"
    r")",
    re.IGNORECASE,
)

GENERIC_TITLE_RE = re.compile(
    r"^\s*("
    r"Actualités|Newsroom|Accessibilité|Contact|Privacy|Politique de confidentialité|Mentions légales|Plan du site"
    r"|利用規約|プライバシーポリシー|アクセスランキング|審議会|政策|統計|Newsletters?|Cookie|Cookies"
    r"|Login|Se connecter|Topics?|Culture|Opinion|March|April|平成\d+年|新着情報一覧|子どもページ"
    r"|ご意見|ランキング|Fonds & investisseurs IA|Acteurs incontournables|Lifestyle|Management|Patrimoine"
    r"|Nikkei Asia|OFFICE PASS"
    r")\s*$",
    re.IGNORECASE,
)

ARTICLE_URL_RE = re.compile(
    r"("
    r"/20\d{2}/\d{1,2}/\d{1,2}/"
    r"|/20\d{2}-\d{1,2}-\d{1,2}"
    r"|/(?:article|articles|story|stories)/"
    r"|/(?:business|economy|finance|markets|tech|technology|politics)/.+"
    r"|/(?:actualites|communiques?-de-presse|press-releases?|news-releases?|release|report/press)/.+"
    r"|/jc/article\?k="
    r"|/fr/statistiques/\d+"
    r"|/news/r\d+/"
    r"|/stf/(?:newpage_|shinsei_)"
    r"|/b_menu/houdou/"
    r"|/report/press/"
    r"|/press/news/20\d{2}/"
    r"|/news/articles/\d+"
    r"|/article/20\d{6}"
    r"|/atcl/"
    r"|/[a-z0-9-]+-\d{6,}/?$"
    r")",
    re.IGNORECASE,
)

ARTICLE_HTML_RE = re.compile(
    r"("
    r"<article\b"
    r"|article:published_time"
    r"|itemprop=[\"']articleBody[\"']"
    r"|@type[\"']?\s*:\s*[\"'](?:NewsArticle|Article|ReportageNewsArticle|BlogPosting)[\"']"
    r"|class=[\"'][^\"']*(?:article-body|article__body|story-body|entry-content|post-content|pressrelease|richtext)[^\"']*[\"']"
    r")",
    re.IGNORECASE,
)


def is_probable_non_article_url(url: str) -> bool:
    if not url:
        return True
    parsed = urlparse(url)
    if parsed.path.lower().endswith((
        ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg",
        ".zip", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    )):
        return True
    return bool(NON_ARTICLE_URL_RE.search(url))


def is_probable_article_url(url: str) -> bool:
    return bool(url and ARTICLE_URL_RE.search(url) and not is_probable_non_article_url(url))


def is_probable_generic_title(title: str) -> bool:
    return bool(title and GENERIC_TITLE_RE.match(title.strip()))


def is_article_body_item(item, spider=None) -> bool:
    url = str(item.get("url") or "")
    title = str(item.get("title") or "")
    raw_html = item.get("raw_html") or ""
    content_plain = item.get("content_plain") or item.get("content") or ""
    publish_time = item.get("publish_time")

    if getattr(spider, "allow_non_article_pages", False):
        return True
    if is_probable_non_article_url(url) or is_probable_generic_title(title):
        return False
    if not raw_html or "<" not in raw_html or len(raw_html) < 500:
        return False
    if not content_plain or len(str(content_plain).strip()) < 120:
        return False

    has_article_html = bool(ARTICLE_HTML_RE.search(raw_html[:500000]))
    has_article_url = is_probable_article_url(url)

    if has_article_url:
        return True

    return bool(publish_time and has_article_html and len(str(content_plain).strip()) >= 300)
