import test from "node:test";
import assert from "node:assert/strict";

import { formatDate, stateClass, summarizeCrawlResult, summarizeTaskResult } from "../lib/formatters.js";

test("formatDate returns placeholder for empty values", () => {
  assert.equal(formatDate(null), "—");
  assert.equal(formatDate(""), "—");
});

test("formatDate preserves invalid date strings", () => {
  assert.equal(formatDate("not-a-date"), "not-a-date");
});

test("stateClass maps task states to display classes", () => {
  assert.equal(stateClass("SUCCESS"), "state-pill state-success");
  assert.equal(stateClass("failure"), "state-pill state-failure");
  assert.equal(stateClass("RETRY"), "state-pill state-active");
  assert.equal(stateClass("unknown"), "state-pill");
});

test("summarizeTaskResult aggregates translation and embedding counts", () => {
  assert.deepEqual(
    summarizeTaskResult({
      translation: { processed: 4, completed: 3, failed: 1 },
      embedding: { processed: 3, completed: 2, failed: 1 }
    }),
    {
      translation: "3/4",
      embedding: "2/3",
      failed: 2
    }
  );
});

test("summarizeTaskResult returns null for empty payloads", () => {
  assert.equal(summarizeTaskResult({}), null);
  assert.equal(summarizeTaskResult(null), null);
});

test("summarizeTaskResult reads backfill payload from pipeline run result", () => {
  assert.deepEqual(
    summarizeTaskResult({
      crawl: { processed: 3, failed: 1 },
      backfill: {
        translation: { processed: 5, completed: 4, failed: 1 },
        embedding: { processed: 4, completed: 4, failed: 0 }
      }
    }),
    {
      translation: "4/5",
      embedding: "4/4",
      failed: 1
    }
  );
});

test("summarizeCrawlResult reads crawl metrics from pipeline run result", () => {
  assert.deepEqual(
    summarizeCrawlResult({
      crawl: { processed: 5, failed: 2 }
    }),
    {
      crawl: "3/5",
      failed: 2
    }
  );
});
