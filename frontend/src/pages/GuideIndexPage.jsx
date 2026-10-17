import React, { useState, useEffect } from 'react';
import { api } from '../api/client';

const LEVEL_COLOR = { L1: '#4caf50', L2: '#8bc34a', L3: '#ffb300', L4: '#ff7043', L5: '#e53935' };

function GuideIndexPage({ active, onOpenArticle }) {
  const [data, setData] = useState({ guides: [], questions: [] });
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (active) {
      setLoading(true);
      api.getGenerated().then(r => {
        setData(r.data || { guides: [], questions: [] });
        setLoading(false);
      }).catch(() => setLoading(false));
    }
  }, [active]);

  if (!active) return null;

  const guides = data.guides || [];
  const questions = data.questions || [];

  return (
    <div className="guide-index">
      <div className="guide-index-head">
        <h2>📖 导读目录</h2>
        <p>已生成的精读导读和泛读检测内容，点击直接阅读</p>
      </div>

      {loading ? (
        <div className="guide-index-empty">加载中…</div>
      ) : (
        <>
          <section className="guide-index-section">
            <h3>📚 精读导读 <span className="guide-index-count">{guides.length}</span></h3>
            {guides.length === 0 ? (
              <div className="guide-index-empty">还没有精读导读，去「精读」页生成第一篇吧</div>
            ) : (
              <div className="guide-index-grid">
                {guides.map(g => (
                  <button
                    key={g.article_id}
                    className="guide-index-card"
                    onClick={() => onOpenArticle('intensive', g.article_id)}
                  >
                    <div className="guide-index-card-title">{g.title}</div>
                    <div className="guide-index-card-meta">
                      <span className="intensive-level" style={{ background: LEVEL_COLOR[g.level] || '#999' }}>{g.level}</span>
                      <span>{g.topic} · {g.word_count}词</span>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </section>

          <section className="guide-index-section">
            <h3>📰 泛读检测 <span className="guide-index-count">{questions.length}</span></h3>
            {questions.length === 0 ? (
              <div className="guide-index-empty">还没有泛读检测，去「泛读」页做第一篇吧</div>
            ) : (
              <div className="guide-index-grid">
                {questions.map(q => (
                  <button
                    key={q.article_id}
                    className="guide-index-card"
                    onClick={() => onOpenArticle('extensive', q.article_id)}
                  >
                    <div className="guide-index-card-title">{q.title}</div>
                    <div className="guide-index-card-meta">
                      <span>{q.word_count}词 · {q.source}</span>
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
