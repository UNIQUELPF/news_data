import { formatDate } from "../lib/formatters";

export default function ArticleOverview({ article }) {
  const isChineseArticle = String(article.language || "").toLowerCase().startsWith("zh");
  const displayTitle = isChineseArticle ? article.title_original : (article.title_translated || article.title_original);
  const displaySummary = isChineseArticle ? null : article.summary_translated;
  const displayContent = isChineseArticle ? article.content_original : (article.content_translated || article.content_original);

  return (
    <div className="article-hero">
      <h1 className="article-hero-title">{displayTitle}</h1>
      <div className="article-meta-tags">
         <span className="meta-tag blue-tag">🏷️ 类别：{article.category || "—"}</span>
         <span className="meta-tag blue-tag">🏢 企业：{article.company || "—"}</span>
         {article.country_code !== 'CHN' && (
            <>
              <span className="meta-tag blue-tag">🌐 国家：{article.country || "—"}</span>
              <span className="meta-tag blue-tag">👥 组织：{article.organization || "—"}</span>
            </>
         )}
         {article.province ? <span className="meta-tag blue-tag">📍 省份：{article.province}</span> : null}
         {article.city ? <span className="meta-tag blue-tag">🏙️ 城市：{article.city}</span> : null}
      </div>
      <div className="article-meta-tags">
         <span className="meta-tag">📅 发布时间：{formatDate(article.publish_time)}</span>
         <a href={article.source_url} target="_blank" rel="noreferrer" className="meta-tag blue-text">🔗 来源链接</a>
      </div>
      <hr className="article-divider" />
      <div className="article-content-body">
         {displaySummary && <p>{displaySummary}</p>}
         <p>{displayContent}</p>
         {!isChineseArticle && article.content_original && (
             <div className="article-original-text">
                <h3>原文</h3>
                <p>{article.content_original}</p>
             </div>
         )}
      </div>
    </div>
  );
}
