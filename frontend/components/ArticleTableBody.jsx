import { formatDate } from "../lib/formatters";

export default function ArticleTableBody({ articles, searchInfo, onOpenArticle, variant = "global" }) {
  const isDomestic = variant === "domestic";

  const getCategoryStyle = (name) => {
    // 1. 定义常见分类的语义化颜色 (H = Hue)
    const presetHues = {
      '经济': 210, // 蓝色
      '金融': 210,
      '科技': 170, // 青色
      '互联网': 170,
      '能源': 45,  // 金色
      '电力': 45,
      '环境': 120, // 绿色
      '社会': 145, // 浅绿
      '政治': 0,   // 红色
      '外交': 330, // 深粉
      '军事': 240, // 灰蓝 (这里饱和度会调低)
      '法规': 280, // 紫色
      '法律': 280,
    };

    let h;
    let s = 75;
    let l = 93;

    if (presetHues[name] !== undefined) {
      h = presetHues[name];
      if (name === '军事') s = 25; // 军事类调低饱和度显稳重
    } else {
      // 2. 兜底逻辑：对生僻分类依然使用哈希算法计算颜色
      let hash = 0;
      for (let i = 0; i < name.length; i++) {
        hash = ((hash << 5) + hash) + name.charCodeAt(i) * 131;
      }
      h = Math.abs(hash % 18) * 20;
    }
    
    return {
      background: `hsl(${h}, ${s}%, ${l}%)`,
      color: `hsl(${h}, 80%, 28%)`,
      border: `1px solid hsl(${h}, 60%, 82%)`
    };
  };

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
                  return (
                    <span 
                      key={idx} 
                      className="category-badge"
                      style={getCategoryStyle(cleanCat)}
                    >
                      {cleanCat}
                    </span>
                  );
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
