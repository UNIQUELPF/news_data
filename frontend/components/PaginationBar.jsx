import { useState, useEffect } from 'react';

export default function PaginationBar({ pagination, onPrevPage, onNextPage, onJumpPage }) {
  const [jumpValue, setJumpValue] = useState(pagination.page || 1);

  useEffect(() => {
    setJumpValue(pagination.page || 1);
  }, [pagination.page]);

  const handleJump = (e) => {
    if (e.key === 'Enter') {
      const page = parseInt(jumpValue);
      if (!isNaN(page) && page >= 1 && page <= pagination.total_pages) {
        onJumpPage(page);
      } else {
        setJumpValue(pagination.page);
      }
    }
  };

  const handleBlur = () => {
    const page = parseInt(jumpValue);
    if (!isNaN(page) && page >= 1 && page <= pagination.total_pages) {
      if (page !== pagination.page) {
        onJumpPage(page);
      }
    } else {
      setJumpValue(pagination.page);
    }
  };

  return (
    <div className="pagination-bar">
      <button className="secondary" disabled={pagination.page <= 1} onClick={() => onJumpPage(1)}>首页</button>
      <button className="secondary" disabled={pagination.page <= 1} onClick={onPrevPage}>上一页</button>
      
      <div className="pagination-jump">
         第 <input 
            className="pagination-input"
            type="number" 
            value={jumpValue} 
            onChange={(e) => setJumpValue(e.target.value)} 
            onKeyDown={handleJump}
            onBlur={handleBlur}
            min="1"
            max={pagination.total_pages}
         /> / {pagination.total_pages || 1} 页
      </div>

      <button className="secondary" disabled={pagination.page >= pagination.total_pages} onClick={onNextPage}>下一页</button>
      <button className="secondary" disabled={pagination.page >= pagination.total_pages} onClick={() => onJumpPage(pagination.total_pages)}>尾页</button>
    </div>
  );
}
