export const ADMIN_TOKEN_STORAGE_KEY = "global-politics-admin-token";
export const ADMIN_ACTOR_STORAGE_KEY = "global-politics-admin-actor";

export const activeTaskStates = ["PENDING", "STARTED", "RETRY"];

export const defaultBackfillForm = {
  spiders_text: "",
  target_language: "zh-CN",
  translate_limit: 20,
  embed_limit: 20,
  force_translate: false,
  force_embed: false
};

export function normalizeRuntimeStatus(payload) {
  return {
    production_ready: Boolean(payload?.production_ready),
    warnings: Array.isArray(payload?.warnings) ? payload.warnings : [],
    translation: {
      mode: payload?.translation?.mode || "placeholder",
      enabled: Boolean(payload?.translation?.enabled),
      model: payload?.translation?.model || "",
      production_ready: Boolean(payload?.translation?.production_ready)
    },
    embedding: {
      provider: payload?.embedding?.provider || "unknown",
      enabled: Boolean(payload?.embedding?.enabled),
      model: payload?.embedding?.model || "",
      production_ready: Boolean(payload?.embedding?.production_ready)
    },
    search: {
      hybrid_weights: payload?.search?.hybrid_weights || null
    }
  };
}

export function applySpiderSelection(form, spiderName, mode = "replace") {
  const normalizedSpider = String(spiderName || "").trim();
  if (!normalizedSpider) {
    return form;
  }

  const nextSpiders = mode === "append"
    ? mergeSpiderCsv(form?.spiders_text, normalizedSpider)
    : normalizedSpider;

  return {
    ...form,
    spiders_text: nextSpiders
  };
}

export function isActiveTaskState(state) {
  return activeTaskStates.includes(String(state || "").toUpperCase());
}

export function selectVisibleTasks(tasks, showRunningOnly) {
  if (!showRunningOnly) return tasks;
  return tasks.filter((item) => isActiveTaskState(item.state));
}

export function combineTaskLists(...taskLists) {
  return taskLists
    .flat()
    .filter(Boolean)
    .sort((left, right) => {
      const leftActive = isActiveTaskState(left.state) ? 1 : 0;
      const rightActive = isActiveTaskState(right.state) ? 1 : 0;
      if (leftActive !== rightActive) return rightActive - leftActive;

      const leftTime = new Date(left.created_at || 0).getTime();
      const rightTime = new Date(right.created_at || 0).getTime();
      if (leftTime !== rightTime) return rightTime - leftTime;

      return String(right.task_id || "").localeCompare(String(left.task_id || ""));
    });
}

export function selectActiveTask(tasks) {
  return tasks.find((item) => isActiveTaskState(item.state)) || null;
}

export function resolveActiveTaskState(activeTaskId, taskDetails, tasks) {
  if (!activeTaskId) return "";
  return String(taskDetails[activeTaskId]?.state || tasks.find((item) => item.task_id === activeTaskId)?.state || "").toUpperCase();
}

export function mergeTaskDetail(tasks, taskId, detail) {
  return tasks.map((item) => (
    item.task_id === taskId
      ? { ...item, ...detail, error_message: detail.error || item.error_message }
      : item
  ));
}

export function serializeSpiderPreset(spiders) {
  return (spiders || []).join(",");
}

export function parseSpiderCsv(value) {
  return String(value || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

export function mergeSpiderCsv(existingValue, presetValue) {
  const merged = [
    ...parseSpiderCsv(existingValue),
    ...parseSpiderCsv(presetValue)
  ];

  return [...new Set(merged)].join(",");
}

export function removeSpiderFromCsv(existingValue, spiderName) {
  return parseSpiderCsv(existingValue)
    .filter((item) => item !== spiderName)
    .join(",");
}

export function summarizeSpiderInput(rawValue) {
  const rawItems = String(rawValue || "")
    .split(",")
    .map((item) => item.trim());
  const nonEmptyItems = rawItems.filter(Boolean);
  const uniqueItems = [...new Set(nonEmptyItems)];

  return {
    total: nonEmptyItems.length,
    unique: uniqueItems.length,
    duplicates: nonEmptyItems.length - uniqueItems.length,
    hasEmptySlots: rawItems.some((item, index) => item === "" && index !== rawItems.length - 1)
  };
}

export function validatePipelineRequestForm(form) {
  const translateLimit = Number(form?.translate_limit || 0);
  const embedLimit = Number(form?.embed_limit || 0);

  if (translateLimit <= 0) {
    return "翻译数量必须大于 0";
  }
  if (embedLimit <= 0) {
    return "向量数量必须大于 0";
  }
  if (form?.execution_mode === "pipeline_run" && parseSpiderCsv(form?.spiders_text).length === 0) {
    return "完整流程至少需要 1 个 spider";
  }
  return "";
}
