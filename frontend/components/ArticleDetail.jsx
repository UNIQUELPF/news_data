import ArticleChunkList from "./ArticleChunkList";
import ArticleOverview from "./ArticleOverview";
import SimilarArticlesList from "./SimilarArticlesList";

export default function ArticleDetail({ articleData, loading, onOpenArticle }) {
  if (!articleData) return null;

  const { article, chunks, similar_articles: similarArticles } = articleData;

  return (
    <div className="detail-card article-detail-container">
      {loading ? (
        <div className="empty">正在加载文章详情...</div>
      ) : (
        <>
          <ArticleOverview article={article} />
          
          <div className="recommendations-section">
            {!chunks && !similarArticles ? (
              <div className="loading-sub">正在寻找相关内容和知识切片...</div>
            ) : (
              <>
                <ArticleChunkList chunks={chunks} />
                <SimilarArticlesList items={similarArticles} onOpenArticle={onOpenArticle} />
              </>
            )}
          </div>
        </>
      )}
    </div>
  );
}
