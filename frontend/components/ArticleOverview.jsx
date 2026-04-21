import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { formatDate } from "../lib/formatters";

export default function ArticleOverview({ article }) {
  const isChineseArticle = String(article.language || "").toLowerCase().startsWith("zh");
  const displayTitle = isChineseArticle ? article.title_original : (article.title_translated || article.title_original);
  
  // Logic: Prefer translated content, then markdown, then original
  const displayContent = article.content_translated || article.content_markdown || article.content_plain || "";
  
  // Extract images
  const images = Array.isArray(article.images) ? article.images : [];
  const heroImage = images.length > 0 ? images[0] : null;

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
      </div>

      <div className="article-meta-tags secondary-meta">
         <span className="meta-tag">📅 发布时间：{formatDate(article.publish_time)}</span>
         <a href={article.source_url} target="_blank" rel="noreferrer" className="meta-tag blue-text">🔗 来源链接</a>
      </div>

      <hr className="article-divider" />

      <div className="article-content-body markdown-content">
          {article.summary_translated && (
            <div className="article-summary-box">
               <strong>摘要：</strong> {article.summary_translated}
            </div>
          )}
          
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {displayContent}
          </ReactMarkdown>

          {!isChineseArticle && article.content_plain && !article.content_translated && (
              <div className="article-original-text">
                 <h3>原文</h3>
                 <div className="original-p-wrap">{article.content_plain}</div>
              </div>
          )}
      </div>
    </div>
  );
}
