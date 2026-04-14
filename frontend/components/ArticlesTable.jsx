import ArticleTableBody from "./ArticleTableBody";
import PaginationBar from "./PaginationBar";

export default function ArticlesTable({
  articles,
  error,
  loading,
  pagination,
  searchInfo,
  variant = "global",
  onOpenArticle,
  onPrevPage,
  onNextPage
}) {
  const isDomestic = variant === "domestic";

  return (
    <div className="table-panel">
      {error ? <div className="error">{error}</div> : null}
      {loading ? <div className="empty">正在加载...</div> : null}
      {!loading ? (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>序号</th>
                <th>标题</th>
                <th>资讯类别</th>
                <th>所涉企业</th>
                <th>{isDomestic ? "所在省" : "国别"}</th>
                <th>{isDomestic ? "所在市" : "组织"}</th>
                <th>更新时间</th>
                <th>来源网址</th>
              </tr>
            </thead>
            <ArticleTableBody articles={articles} searchInfo={searchInfo} onOpenArticle={onOpenArticle} variant={variant} />
          </table>
        </div>
      ) : null}
      <PaginationBar pagination={pagination} onPrevPage={onPrevPage} onNextPage={onNextPage} />
    </div>
  );
}
