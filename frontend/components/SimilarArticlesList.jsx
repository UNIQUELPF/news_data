export default function SimilarArticlesList({ items, onOpenArticle }) {
  return (
    <div className="detail-section">
      <h2>相似文章</h2>
      {items?.length ? items.map((item) => (
        <div key={item.id} className="task-history-card" style={{ marginTop: 10 }}>
          <button className="title-link" onClick={() => onOpenArticle(item.id)}>{item.title}</button>
          <div className="task-meta">{item.country || "—"} / {(Number(item.similarity_score || 0) * 100).toFixed(1)}%</div>
        </div>
      )) : <div className="empty">暂无相似文章</div>}
    </div>
  );
}
