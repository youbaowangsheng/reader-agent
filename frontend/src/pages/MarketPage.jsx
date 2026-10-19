import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import Cover from '../components/Cover';

function MarketPage({ active }) {
  const [data, setData] = useState({ total: 0, categories: [] });
  const [loading, setLoading] = useState(false);
  const [importing, setImporting] = useState({});
  const [imported, setImported] = useState({});
  const [error, setError] = useState('');

  useEffect(() => {
    if (active) loadBooks();
  }, [active]);

  const loadBooks = async (refresh = false) => {
    setLoading(true);
    setError('');
    try {
      const res = await api.getMarketBooks(refresh);
      setData(res.data || { total: 0, categories: [] });
    } catch (err) {
      setError('加载失败：' + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  const handleImport = async (book) => {
    setImporting(prev => ({ ...prev, [book.filename]: true }));
    try {
      const res = await api.importBook(book.pdf_path, book.filename);
      setImported(prev => ({ ...prev, [book.filename]: res.data.article_count || 0 }));
      alert(res.data.message || '已下载并拆分');
    } catch (err) {
      alert('下载失败：' + (err.response?.data?.detail || err.message));
    } finally {
      setImporting(prev => ({ ...prev, [book.filename]: false }));
    }
  };

  if (!active) return null;

  const { categories, total } = data;

  return (
    <div id="page-market" className="page active">
      <div className="market-hero">
        <h3>图书市场</h3>
        <p>共 {total} 期 · 下载后自动拆分进书架，点「评级入库」进精读/泛读</p>
        <button className="btn-ghost market-refresh" onClick={() => loadBooks(true)} disabled={loading}>
          {loading ? '刷新中…' : '🔄 刷新'}
        </button>
      </div>

      {loading ? (
        <div className="loading">加载中…</div>
      ) : error ? (
        <div className="empty-state" style={{ padding: '30px', textAlign: 'center', color: 'var(--text-4)' }}>{error}</div>
      ) : categories.length === 0 ? (
        <div className="market-empty">
          <div className="market-empty-cover">📚</div>
          <h4>暂无图书</h4>
        </div>
      ) : (
        categories.map(cat => (
          <div key={cat.category} className="market-cat">
            <div className="market-cat-head">
              <h4>{cat.name}</h4>
              <span>{cat.books.length} 期</span>
            </div>
            <div className="market-book-grid">
              {cat.books.map(book => (
                <div key={book.pdf_path} className="market-book-card">
                  {book.cover_url ? (
                    <div className="mb-cover">
                      <img src={book.cover_url} alt={book.filename} loading="lazy" />
                    </div>
                  ) : (
                    <Cover title={book.title || book.filename?.replace(/\.pdf$/i, '')} type="图书" subtitle={book.issue || ''} />
                  )}
                  <div className="mb-title">{book.title || book.filename?.replace(/\.pdf$/i, '')}</div>
                  <div className="mb-meta">{book.issue || ''}</div>
                  {imported[book.filename] != null ? (
                    <span className="mb-done">已入库 {imported[book.filename]} 篇 ✓</span>
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
