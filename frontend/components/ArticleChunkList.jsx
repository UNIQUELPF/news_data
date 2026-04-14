export default function ArticleChunkList({ chunks }) {
  return (
    <div className="detail-section">
      <h2>文本分块</h2>
      {chunks?.length ? chunks.map((chunk) => (
        <div key={chunk.chunk_index} className="task-history-card" style={{ marginTop: 10 }}>
          <div className="task-meta">Chunk #{chunk.chunk_index} / tokens {chunk.token_count || 0} / {chunk.embedding_status || "—"}</div>
          <p>{chunk.content_text}</p>
        </div>
      )) : <div className="empty">暂无 chunk 数据</div>}
    </div>
  );
}
