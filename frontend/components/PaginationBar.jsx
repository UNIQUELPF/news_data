export default function PaginationBar({ pagination, onPrevPage, onNextPage }) {
  return (
    <div className="pagination-bar">
      <button className="secondary" disabled={pagination.page <= 1} onClick={onPrevPage}>上一页</button>
      <span className="chip">第 {pagination.page || 1} / {pagination.total_pages || 1} 页</span>
      <button className="secondary" disabled={pagination.page >= pagination.total_pages} onClick={onNextPage}>下一页</button>
    </div>
  );
}
