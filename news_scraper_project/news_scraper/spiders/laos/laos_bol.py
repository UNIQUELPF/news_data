# 老挝中央银行爬虫，抓取英文公告和 PDF 材料。
import re
import subprocess
from datetime import datetime

from news_scraper.spiders.laos.base import LaosBaseSpider


class LaosBolSpider(LaosBaseSpider):
    name = "laos_bol"
    allowed_domains = ["bol.gov.la", "www.bol.gov.la"]
    target_table = "lao_bol"
    start_urls = [
        "https://bol.gov.la/en/fileupload/28-01-2026_1769571479.pdf",
        "https://www.bol.gov.la/en/fileupload/19-08-2025_1755594350.pdf",
        "https://www.bol.gov.la/en/fileupload/17-10-2024_1729133811.pdf",
        "https://www.bol.gov.la/en/fileupload/29-05-2024_1716971673.pdf",
    ]

    def start_requests(self):
        for url in self.start_urls:
            if url in self.seen_urls:
                continue
            self.seen_urls.add(url)
            pdf_bytes = self._fetch_pdf(url)
            if not pdf_bytes:
                continue
            item = self.build_pdf_item(url, pdf_bytes)
            if item:
                yield item

    def _fetch_pdf(self, url):
        try:
            result = subprocess.run(
                [
                    "curl",
                    "-k",
                    "-L",
                    "--http1.1",
                    "--silent",
                    "--show-error",
                    url,
                ],
                capture_output=True,
                timeout=self.request_timeout,
                check=True,
            )
            return result.stdout
        except Exception as exc:
            self.logger.warning(f"PDF fetch failed for {url}: {exc}")
            return b""

    def build_pdf_item(self, url, pdf_bytes):
        filename = url.rsplit("/", 1)[-1]
        title = self._clean_text(filename.replace(".pdf", "").replace("_", " "))
        content = self._extract_pdf_text(pdf_bytes, max_pages=6)
        if not content:
            return None

        match = re.search(r"(\d{2})-(\d{2})-(\d{4})", filename)
        publish_time = None
        if match:
            publish_time = datetime.strptime(match.group(0), "%d-%m-%Y")
            if not self.full_scan and publish_time < self.cutoff_date:
                return None

        response = self._make_response(url, "")
        return self._build_item(
            response=response,
            title=title,
            content=content,
            publish_time=publish_time,
            author="Bank of the Lao PDR",
            language="en",
            section="central_bank",
        )
