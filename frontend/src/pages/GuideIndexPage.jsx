import React, { useState, useEffect } from 'react';
import { api } from '../api/client';

const LEVEL_COLOR = { L1: '#4caf50', L2: '#8bc34a', L3: '#ffb300', L4: '#ff7043', L5: '#e53935' };

function GuideIndexPage({ active, onOpenArticle }) {
  const [intensive, setIntensive] = useState([]);
  const [extensive, setExtensive] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (active) {
      setLoading(true);
      Promise.all([
        api.getIntensiveArticles(),
        api.getExtensiveArticles(),
      ]).then(([ir, er]) => {
        setIntensive(ir.data || []);
        setExtensive(er.data || []);
        setLoading(false);
      }).catch(() => setLoading(false));
    }
  }, [active]);

  if (!active) return null;

  return (
    <div className="guide-index">
      <div className="guide-index-head">
        <h2>📖 导读目录</h2>
        <p>全部拆解文章 · 精读 {intensive.length} 篇 + 泛读 {extensive.length} 篇，点击开始阅读</p>
      </div>

      {loading ? (
        <div className="guide-index-empty">加载中…</div>
      ) : (
        <>
          <section className="guide-index-section">
            <h3>📚 AI精读文章 <span className="guide-index-count">{intensive.length}</span></h3>
            {intensive.length === 0 ? (
              <div className="guide-index-empty">还没有精读文章</div>
            ) : (
              <div className="guide-index-grid">
                {intensive.map(a => (
                  <button
                    key={a.id}
                    className="guide-index-card"
                    onClick={() => onOpenArticle('intensive', a.id)}
                  >
                    <div className="guide-index-card-title">{a.title}</div>
                    <div className="guide-index-card-meta">
                      <span className="intensive-level" style={{ background: LEVEL_COLOR[a.level] || '#999' }}>{a.level}</span>
                      <span>{a.topic} · {a.word_count}词</span>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </section>

          <section className="guide-index-section">
            <h3>📰 AI泛读文章 <span className="guide-index-count">{extensive.length}</span></h3>
            {extensive.length === 0 ? (
              <div className="guide-index-empty">还没有泛读文章</div>
            ) : (
              <div className="guide-index-grid">
                {extensive.map(a => (
                  <button
                    key={a.id}
                    className="guide-index-card"
                    onClick={() => onOpenArticle('extensive', a.id)}
                  >
                    <div className="guide-index-card-title">{a.title}</div>
                    <div className="guide-index-card-meta">
                      <span>{a.word_count}词 · {a.source}</span>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}

export default GuideIndexPage;
