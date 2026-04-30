import io
import json
from datetime import datetime

import dateparser
import requests
import urllib3
from bs4 import BeautifulSoup
from curl_cffi import requests as curl_requests
from pypdf import PdfReader
from scrapy.http import HtmlResponse

from news_scraper.spiders.smart_spider import SmartSpider


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class GermanyBaseSpider(SmartSpider):
    country_code = "DEU"
    country = "德国"
    language = "en"
    source_timezone = "Europe/Berlin"
    start_date = "2025-01-01"
    custom_settings = {
        "DOWNLOAD_DELAY": 0.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 8,
    }
    request_timeout = 30

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.request_headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }

    def _build_item(self, response, title, content, publish_time, author, language, section):
        normalized_time = self.parse_to_utc(publish_time) if publish_time else datetime.utcnow()
        return {
            "url": response.url,
            "title": title,
            "raw_html": self._response_text(response),
            "content": content,
            "content_cleaned": content,
            "content_markdown": content,
            "content_plain": content,
            "publish_time": normalized_time,
            "author": author,
            "language": language or self.language,
            "section": section,
            "country_code": self.country_code,
            "country": self.country,
        }

    def _response_text(self, response):
        try:
            return response.text
        except AttributeError:
            return ""

    def _clean_text(self, value):
        if not value:
            return ""
        return " ".join(str(value).replace("\x00", " ").split()).strip()

    def _parse_datetime(self, value, languages=None):
        if not value:
            return None
        parsed = dateparser.parse(value, languages=languages)
        if not parsed:
            return None
        return self.parse_to_utc(parsed)

    def _fetch(self, url, method="GET", json_data=None, headers=None):
        request_headers = dict(self.request_headers)
        if headers:
            request_headers.update(headers)
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=request_headers,
                json=json_data,
                timeout=self.request_timeout,
                allow_redirects=True,
                verify=False,
            )
            response.raise_for_status()
            return response
        except Exception:
            response = curl_requests.request(
                method,
                url,
                headers=request_headers,
                json=json_data,
                timeout=self.request_timeout,
                allow_redirects=True,
                verify=False,
                impersonate="chrome124",
            )
            response.raise_for_status()
            return response

    def _fetch_html(self, url, method="GET", json_data=None, headers=None):
        return self._fetch(url, method=method, json_data=json_data, headers=headers).text

    def _fetch_json(self, url, method="GET", json_data=None, headers=None):
        response = self._fetch(url, method=method, json_data=json_data, headers=headers)
        try:
            return response.json()
        except Exception:
            return json.loads(response.text)

    def _fetch_bytes(self, url, method="GET", json_data=None, headers=None):
        return self._fetch(url, method=method, json_data=json_data, headers=headers).content

    def _make_response(self, url, html):
        return HtmlResponse(url=url, body=(html or "").encode("utf-8"), encoding="utf-8")

    def _html_to_text(self, html):
        if not html:
            return ""
        soup = BeautifulSoup(html, "html.parser")
        for unwanted in soup.select("script, style, nav, footer, header, aside, form"):
            unwanted.decompose()
        return self._clean_text(soup.get_text(" ", strip=True))

    def _extract_content(self, response, selectors):
        soup = BeautifulSoup(response.text, "html.parser")
        for selector in selectors:
            root = soup.select_one(selector)
            if not root:
                continue
            for unwanted in root.select(
                "script, style, nav, footer, header, aside, form, "
                ".share, .breadcrumb, .gc-byline, .pagedetails, .gc-stp-stp"
            ):
                unwanted.decompose()
            parts = []
            for node in root.find_all(["p", "li", "h2", "h3"], recursive=True):
                text = self._clean_text(node.get_text(" ", strip=True))
                if not text or len(text) < 20:
                    continue
                if text not in parts:
                    parts.append(text)
            if parts:
                return "\n\n".join(parts)
        return ""

    def _extract_blocks(self, response, selectors):
        return self._extract_content(response, selectors)

    def _extract_pdf_text(self, source, max_pages=6):
        try:
            pdf_bytes = source if isinstance(source, (bytes, bytearray)) else self._fetch_bytes(source)
            reader = PdfReader(io.BytesIO(pdf_bytes))
            pages = []
            for page in reader.pages[:max_pages]:
                text = page.extract_text() or ""
                if text.strip():
                    pages.append(self._clean_text(text))
            return "\n\n".join(pages)
        except Exception as exc:
            self.logger.warning(f"PDF parse failed for {self.name}: {exc}")
            return ""
