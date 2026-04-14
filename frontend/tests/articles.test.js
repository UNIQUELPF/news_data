import test from "node:test";
import assert from "node:assert/strict";

import { buildArticleQuery, defaultFilters, normalizeArticleListResponse } from "../lib/articles.js";

test("buildArticleQuery maps UI state to API params", () => {
  assert.deepEqual(
    buildArticleQuery({
      filters: { ...defaultFilters, category: "法规", country: "德国", timeRange: "7d" },
      page: 3,
      query: "欧盟 AI",
      searchMode: "hybrid",
      pageSize: 20
    }),
    {
      q: "欧盟 AI",
      search_mode: "hybrid",
      category: "法规",
      country: "德国",
      country_code: "all",
      organization: "all",
      province: "all",
      city: "all",
      time_range: "7d",
      page: 3,
      page_size: 20
    }
  );
});

test("buildArticleQuery prefers fixed country for domestic views", () => {
  assert.deepEqual(
    buildArticleQuery({
      filters: { ...defaultFilters, category: "经济", country: "德国" },
      fixedCountry: "中国",
      fixedCountryCode: "CHN"
    }),
    {
      q: "",
      search_mode: "keyword",
      category: "经济",
      country: "中国",
      country_code: "CHN",
      organization: "all",
      province: "all",
      city: "all",
      time_range: "all",
      page: 1,
      page_size: 10
    }
  );
});

test("normalizeArticleListResponse fills defaults", () => {
  assert.deepEqual(normalizeArticleListResponse(null), {
    items: [],
    pagination: { page: 1, total: 0, total_pages: 0 },
    search: { mode: "keyword", query: null, weights: null }
  });
});
