import test from "node:test";
import assert from "node:assert/strict";

import {
  activeTaskStates,
  applySpiderSelection,
  combineTaskLists,
  defaultBackfillForm,
  isActiveTaskState,
  mergeSpiderCsv,
  mergeTaskDetail,
  normalizeRuntimeStatus,
  parseSpiderCsv,
  removeSpiderFromCsv,
  resolveActiveTaskState,
  serializeSpiderPreset,
  selectActiveTask,
  selectVisibleTasks,
  summarizeSpiderInput,
  validatePipelineRequestForm
} from "../lib/pipeline.js";

test("activeTaskStates contains the expected running states", () => {
  assert.deepEqual(activeTaskStates, ["PENDING", "STARTED", "RETRY"]);
});

test("defaultBackfillForm includes execution mode fields", () => {
  assert.equal(defaultBackfillForm.execution_mode, "backfill");
  assert.equal(defaultBackfillForm.spiders_text, "");
});

test("normalizeRuntimeStatus fills defaults and keeps configured values", () => {
  assert.deepEqual(
    normalizeRuntimeStatus({
      production_ready: true,
      warnings: ["demo mode"],
      translation: { mode: "llm", enabled: true, model: "gpt-4.1-mini", production_ready: true },
      embedding: { provider: "local", enabled: true, model: "BAAI/bge-m3", production_ready: false },
      search: { hybrid_weights: { keyword: 0.4, semantic: 0.6 } }
    }),
    {
      production_ready: true,
      warnings: ["demo mode"],
      translation: { mode: "llm", enabled: true, model: "gpt-4.1-mini", production_ready: true },
      embedding: { provider: "local", enabled: true, model: "BAAI/bge-m3", production_ready: false },
      search: { hybrid_weights: { keyword: 0.4, semantic: 0.6 } }
    }
  );

  assert.deepEqual(
    normalizeRuntimeStatus(null),
    {
      production_ready: false,
      warnings: [],
      translation: { mode: "placeholder", enabled: false, model: "", production_ready: false },
      embedding: { provider: "unknown", enabled: false, model: "", production_ready: false },
      search: { hybrid_weights: null }
    }
  );
});

test("applySpiderSelection switches to pipeline mode and replaces or appends spiders", () => {
  assert.deepEqual(
    applySpiderSelection(defaultBackfillForm, "usa_reuters", "replace"),
    {
      ...defaultBackfillForm,
      execution_mode: "pipeline_run",
      spiders_text: "usa_reuters"
    }
  );

  assert.deepEqual(
    applySpiderSelection(
      { ...defaultBackfillForm, execution_mode: "pipeline_run", spiders_text: "malaysia_enanyang" },
      "usa_reuters",
      "append"
    ),
    {
      ...defaultBackfillForm,
      execution_mode: "pipeline_run",
      spiders_text: "malaysia_enanyang,usa_reuters"
    }
  );
});

test("isActiveTaskState normalizes input", () => {
  assert.equal(isActiveTaskState("started"), true);
  assert.equal(isActiveTaskState("SUCCESS"), false);
});

test("selectVisibleTasks filters only running tasks when requested", () => {
  const tasks = [
    { task_id: "1", state: "PENDING" },
    { task_id: "2", state: "SUCCESS" },
    { task_id: "3", state: "RETRY" }
  ];

  assert.deepEqual(selectVisibleTasks(tasks, true), [
    { task_id: "1", state: "PENDING" },
    { task_id: "3", state: "RETRY" }
  ]);
  assert.deepEqual(selectVisibleTasks(tasks, false), tasks);
});

test("selectActiveTask returns the first running task", () => {
  assert.deepEqual(
    selectActiveTask([
      { task_id: "1", state: "SUCCESS" },
      { task_id: "2", state: "STARTED" },
      { task_id: "3", state: "RETRY" }
    ]),
    { task_id: "2", state: "STARTED" }
  );
});

test("resolveActiveTaskState prefers detail payload over list payload", () => {
  assert.equal(
    resolveActiveTaskState(
      "2",
      { "2": { state: "REVOKED" } },
      [{ task_id: "2", state: "STARTED" }]
    ),
    "REVOKED"
  );
});

test("mergeTaskDetail updates matching task and preserves others", () => {
  assert.deepEqual(
    mergeTaskDetail(
      [
        { task_id: "1", state: "PENDING" },
        { task_id: "2", state: "STARTED", error_message: "" }
      ],
      "2",
      { state: "FAILURE", error: "boom" }
    ),
    [
      { task_id: "1", state: "PENDING" },
      { task_id: "2", state: "FAILURE", error_message: "boom", error: "boom" }
    ]
  );
});

test("combineTaskLists prioritizes running tasks and then newest created_at", () => {
  const combined = combineTaskLists(
    [
      { task_id: "1", state: "SUCCESS", created_at: "2026-04-09T10:00:00" },
      { task_id: "2", state: "PENDING", created_at: "2026-04-09T09:00:00" }
    ],
    [
      { task_id: "3", state: "FAILURE", created_at: "2026-04-09T11:00:00" }
    ]
  );

  assert.deepEqual(combined.map((item) => item.task_id), ["2", "3", "1"]);
});

test("serializeSpiderPreset joins spiders as csv", () => {
  assert.equal(serializeSpiderPreset(["a", "b", "c"]), "a,b,c");
  assert.equal(serializeSpiderPreset([]), "");
});

test("mergeSpiderCsv appends unique spiders and normalizes whitespace", () => {
  assert.equal(mergeSpiderCsv("a, b", "b,c , d"), "a,b,c,d");
  assert.equal(mergeSpiderCsv("", "x, y"), "x,y");
});

test("parseSpiderCsv normalizes csv to spider array", () => {
  assert.deepEqual(parseSpiderCsv("a, b,, c "), ["a", "b", "c"]);
  assert.deepEqual(parseSpiderCsv(""), []);
});

test("removeSpiderFromCsv removes a single spider from csv", () => {
  assert.equal(removeSpiderFromCsv("a,b,c", "b"), "a,c");
  assert.equal(removeSpiderFromCsv("a", "a"), "");
});

test("summarizeSpiderInput counts unique spiders and warnings", () => {
  assert.deepEqual(summarizeSpiderInput("a, b,, a ,c"), {
    total: 4,
    unique: 3,
    duplicates: 1,
    hasEmptySlots: true
  });
});

test("validatePipelineRequestForm rejects empty pipeline spiders and invalid limits", () => {
  assert.equal(
    validatePipelineRequestForm({
      execution_mode: "pipeline_run",
      spiders_text: "",
      translate_limit: 10,
      embed_limit: 10
    }),
    "完整流程至少需要 1 个 spider"
  );
  assert.equal(
    validatePipelineRequestForm({
      execution_mode: "backfill",
      spiders_text: "",
      translate_limit: 0,
      embed_limit: 10
    }),
    "翻译数量必须大于 0"
  );
  assert.equal(
    validatePipelineRequestForm({
      execution_mode: "backfill",
      spiders_text: "",
      translate_limit: 10,
      embed_limit: 0
    }),
    "向量数量必须大于 0"
  );
  assert.equal(
    validatePipelineRequestForm({
      execution_mode: "pipeline_run",
      spiders_text: "a,b",
      translate_limit: 10,
      embed_limit: 10
    }),
    ""
  );
});
