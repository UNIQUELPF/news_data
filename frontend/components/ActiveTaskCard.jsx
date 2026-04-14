import { stateClass, summarizeCrawlResult, summarizeTaskResult } from "../lib/formatters";

export default function ActiveTaskCard({ activeTask, taskDetail, onCancelTask }) {
  if (!activeTask) return null;

  const summary = summarizeTaskResult(taskDetail?.result || activeTask.result);
  const crawlSummary = summarizeCrawlResult(taskDetail?.result || activeTask.result);

  return (
    <div className="active-task" style={{ marginTop: 14 }}>
      <div className="panel-head">
        <h2>当前运行中的任务</h2>
        <span className={stateClass(activeTask.state)}>{activeTask.state}</span>
      </div>
      <div className="task-meta">
        <div>{activeTask.task_name}</div>
        <div>类型 {activeTask.task_type || "unknown"}</div>
        <div>{activeTask.task_id}</div>
        <div>操作人 {activeTask.requested_by || "未填写"} / {activeTask.request_ip || "unknown ip"}</div>
      </div>
      {summary ? (
        <div className="summary-grid" style={{ marginTop: 12 }}>
          {crawlSummary ? (
            <div className="summary-card">
              <div className="muted">抓取</div>
              <strong>{crawlSummary.crawl}</strong>
            </div>
          ) : null}
          <div className="summary-card">
            <div className="muted">翻译</div>
            <strong>{summary.translation}</strong>
          </div>
          <div className="summary-card">
            <div className="muted">向量</div>
            <strong>{summary.embedding}</strong>
          </div>
            <div className="summary-card">
              <div className="muted">失败</div>
              <strong>{Math.max(summary.failed, crawlSummary?.failed || 0)}</strong>
            </div>
          </div>
        ) : null}
      <div className="inline-actions" style={{ marginTop: 12 }}>
        <button className="danger" onClick={() => onCancelTask(activeTask.task_id)}>取消任务</button>
      </div>
    </div>
  );
}
