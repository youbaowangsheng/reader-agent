import React, { useState, useEffect } from 'react';
import { api } from '../api/client';

function MarketPage({ active }) {
  const [data, setData] = useState({ total: 0, categories: [], oss_ready: false });
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (active) loadBooks();
  }, [active]);

  const loadBooks = async () => {
    setLoading(true);
    try {
      const res = await api.getMarketBooks();
      setData(res.data || { total: 0, categories: [], oss_ready: false });
    } catch (err) {
      setData({ total: 0, categories: [], oss_ready: false });
    } finally {
      setLoading(false);
    }
  };

  if (!active) return null;

  const { categories, total, oss_ready } = data;

  return (
    <div id="page-market" className="page active">
      <div className="market-hero">
        <h3>图书市场</h3>
        <p>英语杂志 / 期刊书库 · 内容来自阿里云 OSS</p>
      </div>

      {loading ? (
        <div className="loading">加载中…</div>
      ) : !oss_ready ? (
        <div className="market-empty">
          <div className="market-empty-cover">📚</div>
          <h4>图书市场建设中</h4>
          <p>内容将从阿里云 OSS 加载，配置好后这里会显示图书封面</p>
        </div>
      ) : total === 0 ? (
        <div className="market-empty">
          <div className="market-empty-cover">📚</div>
          <h4>暂无图书</h4>
        </div>
      ) : (
        categories.map(cat => (
          <div key={cat.category} className="market-cat">
            <div className="market-cat-head">
              <h4>{cat.name}</h4>
              <span>{cat.books.length} 本</span>
            </div>
            <div className="market-book-grid">
              {cat.books.map(book => (
                <div key={book.title || book.pdf_url} className="market-book-card">
                  <div className="mb-cover">
                    {book.cover_url ? (
                      <img src={book.cover_url} alt={book.title} loading="lazy" />
                    ) : (
                      <span className="mb-cover-placeholder">📖</span>
                    )}
                  </div>
                  <div className="mb-title">{book.title}</div>
                  <div className="mb-meta">{book.issue || ''}</div>
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
