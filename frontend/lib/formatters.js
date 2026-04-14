export function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", { hour12: false });
}

export function stateClass(state) {
  const normalized = String(state || "").toUpperCase();
  if (["SUCCESS"].includes(normalized)) return "state-pill state-success";
  if (["FAILURE", "ERROR"].includes(normalized)) return "state-pill state-failure";
  if (["PENDING", "STARTED", "RETRY", "REVOKED"].includes(normalized)) return "state-pill state-active";
  return "state-pill";
}

export function summarizeTaskResult(result) {
  if (!result || typeof result !== "object") return null;
  const payload = result.backfill || result;
  const translation = payload.translation || {};
  const embedding = payload.embedding || {};
  const processed = Number(translation.processed || 0) + Number(embedding.processed || 0);
  const completed = Number(translation.completed || 0) + Number(embedding.completed || 0);
  const failed = Number(translation.failed || 0) + Number(embedding.failed || 0);
  if (!processed && !completed && !failed) return null;
  return {
    translation: `${Number(translation.completed || 0)}/${Number(translation.processed || 0)}`,
    embedding: `${Number(embedding.completed || 0)}/${Number(embedding.processed || 0)}`,
    failed
  };
}

export function summarizeCrawlResult(result) {
  if (!result || typeof result !== "object") return null;
  const crawl = result.crawl || {};
  const processed = Number(crawl.processed || 0);
  const failed = Number(crawl.failed || 0);
  if (!processed && !failed) return null;
  return {
    crawl: `${processed - failed}/${processed}`,
    failed
  };
}
