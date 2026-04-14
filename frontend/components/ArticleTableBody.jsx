import { formatDate } from "../lib/formatters";

export default function ArticleTableBody({ articles, searchInfo, onOpenArticle, variant = "global" }) {
  const isDomestic = variant === "domestic";

  return (
    <tbody>
      {articles.map((item) => (
        <tr key={item.id}>
          <td className="table-id">{item.id}</td>
          <td>
            <button className="title-link" onClick={() => onOpenArticle(item.id)}>{item.title}</button>
            <div className="score-row" style={{ marginTop: 8 }}>
              {searchInfo.mode !== "keyword" ? <span className="score-pill">语义 {(Number(item.semantic_score || 0) * 100).toFixed(1)}%</span> : null}
              {searchInfo.mode === "hybrid" ? <span className="score-pill">关键词 {Number(item.keyword_score || 0).toFixed(0)}</span> : null}
            </div>
          </td>
          <td>
            {item.category ? (
              <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                {item.category.split(',').map((cat, idx) => {
                  const cleanCat = cat.trim();
                  return <span key={idx} className={`category-badge category-${cleanCat}`}>{cleanCat}</span>;
                })}
              </div>
            ) : "—"}
          </td>
          <td>
            {item.company ? (
              <div 
                title={item.company.split(',').join('\n')}
                style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', maxWidth: '300px' }}
              >
                {(() => {
                  const companies = item.company.split(',').map(c => c.trim()).filter(Boolean);
                  const displayLimit = 3;
                  const visible = companies.slice(0, displayLimit);
                  const extraCount = companies.length - displayLimit;
                  
                  return (
                    <>
                      {visible.map((company, idx) => (
                        <span key={idx} className="org-badge" style={{ fontSize: '12px', minHeight: '28px' }}>
                          {company}
                        </span>
                      ))}
                      {extraCount > 0 && (
                        <span className="org-badge" style={{ fontSize: '12px', minHeight: '28px', background: '#f1f5f9', color: '#64748b' }}>
                          +{extraCount}
                        </span>
                      )}
                    </>
                  );
                })()}
              </div>
            ) : "—"}
          </td>
          <td>{isDomestic ? (item.province || "—") : (item.country || "—")}</td>
          <td>{isDomestic ? (item.city || "—") : <span className="org-badge">{item.organization || "—"}</span>}</td>
          <td>{formatDate(item.publish_time)}</td>
          <td>
            {item.source_url ? (
              <a className="source-link" href={item.source_url} rel="noreferrer" target="_blank">链接</a>
            ) : "—"}
          </td>
        </tr>
      ))}
    </tbody>
  );
}
