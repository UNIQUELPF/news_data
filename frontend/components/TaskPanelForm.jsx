import { useState } from "react";
import { parseSpiderCsv, removeSpiderFromCsv, summarizeSpiderInput } from "../lib/pipeline";

export default function TaskPanelForm({
  backfillForm,
  onBackfillFormChange,
  onIngest,
  onProcessGlobal,
  onProcessDomestic,
  onProcessEmbed,
  availableSpiders = []
}) {
  const [isSpiderDropdownOpen, setIsSpiderDropdownOpen] = useState(false);
  const [spiderSearch, setSpiderSearch] = useState("");

  const selectedSpiders = parseSpiderCsv(backfillForm.spiders_text);
  const spiderSummary = summarizeSpiderInput(backfillForm.spiders_text);

  const filteredSpiders = availableSpiders.filter(s =>
    s.toLowerCase().includes(spiderSearch.toLowerCase())
  );

  const toggleSpider = (spiderName) => {
    if (selectedSpiders.includes(spiderName)) {
      onBackfillFormChange("spiders_text", removeSpiderFromCsv(backfillForm.spiders_text, spiderName));
    } else {
      const newList = [...selectedSpiders, spiderName].join(",");
      onBackfillFormChange("spiders_text", newList);
    }
  };

  return (
    <div className="task-panel-layout">
      {/* --- Section 1: Ingestion --- */}
      <div className="task-section">
        <div className="section-header">
          <h3 className="section-title">📡 数据采集端 (Acquisition)</h3>
          <button onClick={onIngest} className="primary-action-btn">
            开始抓取 (Ingest)
          </button>
        </div>

        <div className="field" style={{ marginTop: '12px' }}>
          <label>Spider 列表 (选中的爬虫将立即执行)</label>
          <div className="multi-select-container">
            <button
              className="select-trigger"
              onClick={() => setIsSpiderDropdownOpen(!isSpiderDropdownOpen)}
              type="button"
            >
              <span>{selectedSpiders.length ? `已选择 ${selectedSpiders.length} 个爬虫` : '点击选择爬虫...'}</span>
              <span className={`arrow ${isSpiderDropdownOpen ? 'up' : 'down'}`}>▼</span>
            </button>

            {isSpiderDropdownOpen && (
              <div className="select-dropdown">
                <div className="dropdown-search">
                  <input
                    placeholder="搜索爬虫..."
                    value={spiderSearch}
                    onChange={e => setSpiderSearch(e.target.value)}
                    autoFocus
                  />
                </div>
                <div className="dropdown-list">
                  {filteredSpiders.map(spider => (
                    <label key={spider} className="dropdown-item">
                      <input
                        type="checkbox"
                        checked={selectedSpiders.includes(spider)}
                        onChange={() => toggleSpider(spider)}
                      />
                      <span>{spider}</span>
                    </label>
                  ))}
                  {filteredSpiders.length === 0 && (
                    <div className="empty-search">未找到匹配的爬虫</div>
                  )}
                </div>
              </div>
            )}
          </div>

          <div className="spider-summary-row">
            <button className="text-action-link" onClick={() => onBackfillFormChange("spiders_text", availableSpiders.join(","))}>全选</button>
            <button className="text-action-link" onClick={() => onBackfillFormChange("spiders_text", "")}>取消全选</button>
            <span className="chip" style={{ marginLeft: 'auto' }}>共有 {availableSpiders.length} 个爬虫</span>
          </div>



          {selectedSpiders.length ? (
            <div className="selected-spider-list">
              {selectedSpiders.map((spiderName) => (
                <button
                  key={spiderName}
                  className="selected-spider-chip"
                  onClick={() => onBackfillFormChange("spiders_text", removeSpiderFromCsv(backfillForm.spiders_text, spiderName))}
                  type="button"
                >
                  {spiderName} <span>×</span>
                </button>
              ))}
            </div>
          ) : null}
        </div>
      </div>

      {/* --- Section 2: Processing --- */}
      <div className="task-section">
        <div className="section-header">
          <h3 className="section-title">🧠 知识加工端 (Processing)</h3>
        </div>
        <div className="task-grid">
          <div className="field">
            <label>处理上限 (条数)</label>
            <input type="number" value={backfillForm.translate_limit} onChange={(event) => onBackfillFormChange("translate_limit", Number(event.target.value || 0))} />
          </div>
          <div className="field">
            <label>强制重算</label>
            <select value={String(backfillForm.force_translate)} onChange={(event) => onBackfillFormChange("force_translate", event.target.value === "true")}>
              <option value="false">否 (仅处理待处理文章)</option>
              <option value="true">是 (覆盖已有结果)</option>
            </select>
          </div>
          <div className="field">
            <label>全球资讯精炼 (外文)</label>
            <button className="secondary" onClick={onProcessGlobal} style={{ width: '100%' }}>
              🌍 全球翻译 + 摘要
            </button>
          </div>
          <div className="field">
            <label>国内政经识别 (中文)</label>
            <button className="secondary" onClick={onProcessDomestic} style={{ width: '100%' }}>
              🇨🇳 国内元数据回填
            </button>
          </div>
        </div>
      </div>

      {/* --- Section 3: Indexing --- */}
      <div className="task-section">
        <div className="section-header">
          <h3 className="section-title">🔍 搜索增强端 (Indexing)</h3>
          <button onClick={onProcessEmbed} className="primary-action-btn action-embed">
            生成语义索引 (Embed)
          </button>
        </div>
        <div className="task-grid">
          <div className="field">
            <label>向量上限 (条数)</label>
            <input type="number" value={backfillForm.embed_limit} onChange={(event) => onBackfillFormChange("embed_limit", Number(event.target.value || 0))} />
          </div>
          <div className="field">
            <label>向量强制重算</label>
            <select value={String(backfillForm.force_embed)} onChange={(event) => onBackfillFormChange("force_embed", event.target.value === "true")}>
              <option value="false">否</option>
              <option value="true">是</option>
            </select>
          </div>
        </div>
      </div>

      <style jsx>{`
        .task-panel-layout {
          display: flex;
          flex-direction: column;
          gap: 24px;
        }
        .task-section {
          background: #f8fafc;
          border-radius: 12px;
          padding: 20px;
          border: 1px solid #e2e8f0;
        }
        .section-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 16px;
          border-bottom: 1px solid #e2e8f0;
          padding-bottom: 12px;
        }
        .section-title {
          margin: 0;
          font-size: 1.1rem;
          color: #1e293b;
          font-weight: 600;
        }
        .primary-action-btn {
          background: #2563eb;
          color: white;
          padding: 8px 16px;
          border-radius: 6px;
          font-size: 0.9rem;
          font-weight: 600;
        }
        .primary-action-btn:hover {
          background: #1d4ed8;
        }
        .action-embed {
          background: #059669;
        }
        .action-embed:hover {
          background: #047857;
        }
        .selected-spider-list {
          display: flex;
          flex-wrap: wrap;
          gap: 6px;
          margin-top: 12px;
          padding: 8px;
          background: white;
          border-radius: 8px;
          border: 1px dashed #cbd5e1;
        }
        .multi-select-container {
          position: relative;
          width: 100%;
        }
        .select-trigger {
          width: 100%;
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 10px 14px;
          background: white;
          border: 1px solid #cbd5e1;
          border-radius: 6px;
          cursor: pointer;
          text-align: left;
          font-size: 0.95rem;
          color: #334155;
        }
        .select-trigger:hover {
          border-color: #94a3b8;
        }
        .select-dropdown {
          position: absolute;
          top: 100%;
          left: 0;
          right: 0;
          z-index: 100;
          background: white;
          border: 1px solid #cbd5e1;
          border-radius: 6px;
          margin-top: 4px;
          box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
          max-height: 400px;
          display: flex;
          flex-direction: column;
        }
        .dropdown-search {
          padding: 8px;
          border-bottom: 1px solid #e2e8f0;
        }
        .dropdown-search input {
          width: 100%;
          padding: 6px 10px;
          border: 1px solid #e2e8f0;
          border-radius: 4px;
          font-size: 0.9rem;
        }
        .dropdown-list {
          overflow-y: auto;
          flex: 1;
          padding: 4px 0;
        }
        .dropdown-item {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 8px 12px;
          cursor: pointer;
          font-size: 0.9rem;
          transition: background 0.2s;
        }
        .dropdown-item:hover {
          background: #f1f5f9;
        }
        .dropdown-item input {
          width: 16px;
          height: 16px;
          cursor: pointer;
        }
        .empty-search {
          padding: 16px;
          text-align: center;
          color: #64748b;
          font-size: 0.9rem;
        }
        .text-action-link {
          background: none;
          border: none;
          color: #2563eb;
          text-decoration: underline;
          padding: 0;
          font-size: 0.85rem;
          cursor: pointer;
          min-height: auto;
        }
        .text-action-link:hover {
          color: #1d4ed8;
        }
        .arrow {
          font-size: 0.7rem;
          transition: transform 0.2s;
        }
        .arrow.up {
          transform: rotate(180deg);
        }
        .preset-row {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-top: 12px;
        }
        .preset-row strong {
          font-size: 0.85rem;
          color: #64748b;
        }
      `}</style>
    </div>
  );
}
