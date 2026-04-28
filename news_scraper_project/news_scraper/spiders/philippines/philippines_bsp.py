# 菲律宾bsp爬虫，负责抓取对应站点、机构或栏目内容。

import json

import scrapy

from news_scraper.spiders.philippines.base import PhilippinesBaseSpider


class PhilippinesBspSpider(PhilippinesBaseSpider):
    name = "philippines_bsp"

    country_code = 'PHL'

    country = '菲律宾'
    allowed_domains = ["bsp.gov.ph", "www.bsp.gov.ph"]
    api_base = "https://www.bsp.gov.ph/_api/web/lists/getbytitle('Media Releases and Advisories')/items"
    start_urls = [f"{api_base}?$select=ID,Title,PDate&$orderby=PDate desc&$top=20"]

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(
                url,
                callback=self.parse_listing,
                headers={"Accept": "application/json;odata=verbose"},
            )

    def parse_listing(self, response):
        data = json.loads(response.text or "{}").get("d", {})
        for row in data.get("results", []):
            item_id = row.get("ID") or row.get("Id")
            title = self._clean_text(row.get("Title"))
            publish_time = self._parse_datetime(row.get("PDate"), languages=["en"])
            if not item_id or not title:
                continue
            if publish_time and not self.full_scan and publish_time < self.cutoff_date:
                continue

            detail_url = (
                "https://www.bsp.gov.ph/SitePages/MediaAndResearch/"
                f"MediaDisp.aspx?ItemId={item_id}"
            )
            api_url = (
                f"{self.api_base}({item_id})"
                "?$select=Title,PDate,Content"
            )
            if not self.should_process(detail_url):
                continue
            yield scrapy.Request(
                api_url,
                callback=self.parse_detail,
                headers={"Accept": "application/json;odata=verbose"},
                meta={"detail_url": detail_url},
            )

    def parse_detail(self, response):
        row = json.loads(response.text or "{}").get("d", {})
        title = self._clean_text(row.get("Title"))
        if not title:
            return

        publish_time = self._parse_datetime(row.get("PDate"), languages=["en"])
        if publish_time and not self.full_scan and publish_time < self.cutoff_date:
            return

        content = self._clean_text(self._html_to_text(row.get("Content") or ""))
        if not content:
            return

        yield self._build_item(
            response=self._make_response(response.meta["detail_url"], ""),
            title=title,
            content=content,
            publish_time=publish_time,
            author="Bangko Sentral ng Pilipinas",
            language="en",
            section="central_bank",
        )
