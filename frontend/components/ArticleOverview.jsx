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
  let heroImage = images.length > 0 ? images[0] : null;
  
  // If the hero image is already inside the content markdown, 
  // don't show it again as a separate hero image to avoid duplication.
  if (heroImage && typeof displayContent === 'string' && displayContent.includes(heroImage)) {
    heroImage = null;
  }

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

      {heroImage && (
        <div className="article-main-image-container" style={{ marginBottom: '24px', textAlign: 'center' }}>
          <img 
            src={heroImage} 
            alt={displayTitle} 
            referrerPolicy="no-referrer"
            className="article-featured-image"
            style={{ 
              maxWidth: '100%', 
              maxHeight: '500px', 
              borderRadius: '12px', 
              boxShadow: '0 4px 20px rgba(0,0,0,0.1)',
              objectFit: 'cover'
            }} 
          />
        </div>
      )}

      <div className="article-content-body markdown-content">
          {article.summary_translated && (
            <div className="article-summary-box">
               <strong>摘要：</strong> {article.summary_translated}
            </div>
          )}
          
          <ReactMarkdown 
            remarkPlugins={[remarkGfm]}
            components={{
              img: ({node, ...props}) => <img {...props} referrerPolicy="no-referrer" style={{maxWidth: '100%'}} />
            }}
          >
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
