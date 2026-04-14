import test from "node:test";
import assert from "node:assert/strict";

import { buildRequestUrl } from "../lib/api.js";

test("buildRequestUrl appends accepted query params", () => {
  const url = buildRequestUrl(
    "/api/v1/articles",
    {
      q: "欧盟 AI",
      page: 2,
      category: "法规",
      country_code: "DEU"
    },
    "http://127.0.0.1:8000"
  );

  assert.equal(
    url.toString(),
    "http://127.0.0.1:8000/api/v1/articles?q=%E6%AC%A7%E7%9B%9F+AI&page=2&category=%E6%B3%95%E8%A7%84&country_code=DEU"
  );
});

test("buildRequestUrl skips empty and all-like query params", () => {
  const url = buildRequestUrl(
    "/api/v1/articles",
    {
      q: "",
      country: "all",
      country_code: "all",
      page: 1,
      organization: null
    },
    "http://127.0.0.1:8000"
  );

  assert.equal(url.toString(), "http://127.0.0.1:8000/api/v1/articles?page=1");
});
