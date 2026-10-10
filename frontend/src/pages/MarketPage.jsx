import React, { useState, useEffect } from 'react';
import { api } from '../api/client';

function MarketPage({ active, onOpenPaper }) {
  const [categories, setCategories] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [importing, setImporting] = useState({});
  const [imported, setImported] = useState({});

  useEffect(() => {
    if (active) loadBooks();
  }, [active]);

  const loadBooks = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await api.getMarketBooks();
      setCategories(res.data.categories || []);
      setTotal(res.data.total || 0);
    } catch (err) {
      setError('加载失败：' + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  const formatSize = (bytes) => {
    if (!bytes) return '';
    if (bytes > 1024 * 1024) return (bytes / 1024 / 1024).toFixed(1) + ' MB';
    return (bytes / 1024).toFixed(0) + ' KB';
  };

  const handleImport = async (book) => {
    setImporting(prev => ({ ...prev, [book.filename]: true }));
    try {
      const res = await api.importBook(book.pdf_path, book.filename);
      setImported(prev => ({ ...prev, [book.filename]: true }));
    } catch (err) {
      alert('下载失败：' + (err.response?.data?.detail || err.message));
    } finally {
      setImporting(prev => ({ ...prev, [book.filename]: false }));
    }
  };

  if (!active) return null;

  return (
    <div id="page-market" className="page active">
      <div className="market-hero">
        <h3>英语杂志书库</h3>
        <p>共 {total} 期 · 来自 GitHub 仓库，下载到书架后自动解析生成 AI 导读</p>
      </div>

      {loading ? (
        <div className="loading">加载中…</div>
      ) : error ? (
        <div className="empty-state" style={{ padding: '30px', textAlign: 'center', color: 'var(--text-4)' }}>{error}</div>
      ) : (
        categories.map(cat => (
          <div key={cat.category} className="market-cat">
            <div className="market-cat-head">
              <h4>{cat.name}</h4>
              <span>{cat.books.length} 期</span>
            </div>
            <div className="market-book-list">
              {cat.books.map(book => (
                <div key={book.pdf_path} className="market-book-item">
                  <div className="mb-info">
                    <div className="mb-name">{book.filename.replace(/\.pdf$/i, '')}</div>
                    <div className="mb-meta">{book.issue} · {formatSize(book.size)}</div>
                  </div>
                  {imported[book.filename] ? (
                    <span className="mb-done">已下载 ✓ 去「书架」点 AI 阅读</span>
                  ) : (
                    <button
                      className="btn-add"
                      disabled={importing[book.filename]}
                      onClick={() => handleImport(book)}
                    >
                      {importing[book.filename] ? '下载中…' : '↓ 下载到书架'}
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>
        ))
      )}
    </div>
  );
}

export default MarketPage;
