import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import Cover from '../components/Cover';

const LEVEL_COLOR = { L1: '#4caf50', L2: '#8bc34a', L3: '#ffb300', L4: '#ff7043', L5: '#e53935' };

function GuideIndexPage({ active, onOpenArticle }) {
  const [tab, setTab] = useState('intensive');
  const [intensive, setIntensive] = useState([]);
  const [extensive, setExtensive] = useState([]);
  const [papers, setPapers] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (active) {
      setLoading(true);
      Promise.all([
        api.getIntensiveArticles(),
        api.getExtensiveArticles(),
        api.getPapers(),
      ]).then(([ir, er, pr]) => {
        setIntensive(ir.data || []);
        setExtensive(er.data || []);
        setPapers(pr.data || []);
        setLoading(false);
      }).catch(() => setLoading(false));
    }
  }, [active]);

  if (!active) return null;

  const readyPapers = papers.filter(p => p.status === 'ready');

  return (
    <div className="guide-index">
      <div className="guide-index-head">
        <h2>📖 首页导读</h2>
        <p>三种阅读能力，选一种开始</p>
      </div>

      <div className="guide-index-tabs">
        <button className={`guide-index-tab ${tab === 'intensive' ? 'active' : ''}`} onClick={() => setTab('intensive')}>
          AI精读 <span className="guide-index-tab-count">{intensive.length}</span>
        </button>
        <button className={`guide-index-tab ${tab === 'extensive' ? 'active' : ''}`} onClick={() => setTab('extensive')}>
          AI泛读 <span className="guide-index-tab-count">{extensive.length}</span>
        </button>
        <button className={`guide-index-tab ${tab === 'papers' ? 'active' : ''}`} onClick={() => setTab('papers')}>
          原文阅读 <span className="guide-index-tab-count">{readyPapers.length}</span>
        </button>
      </div>

      {loading ? (
        <div className="guide-index-empty">加载中…</div>
      ) : tab === 'intensive' ? (
        <div className="guide-index-grid">
          {intensive.length === 0 && <div className="guide-index-empty">还没有精读文章</div>}
          {intensive.map(a => (
            <button key={a.id} className="guide-index-card" onClick={() => onOpenArticle('intensive', a.id)}>
              <Cover title={a.title} type="AI精读" subtitle={a.topic || a.level || ''} />
              <div className="guide-index-card-info">
                <div className="guide-index-card-title">{a.title}</div>
                <div className="guide-index-card-meta">
                  <span className="intensive-level" style={{ background: LEVEL_COLOR[a.level] || '#999' }}>{a.level}</span>
                  <span>{a.topic} · {a.word_count}词</span>
                </div>
              </div>
            </button>
          ))}
        </div>
      ) : tab === 'extensive' ? (
        <div className="guide-index-grid">
          {extensive.length === 0 && <div className="guide-index-empty">还没有泛读文章</div>}
          {extensive.map(a => (
            <button key={a.id} className="guide-index-card" onClick={() => onOpenArticle('extensive', a.id)}>
              <Cover title={a.title} type="AI泛读" subtitle={a.source || ''} />
              <div className="guide-index-card-info">
                <div className="guide-index-card-title">{a.title}</div>
                <div className="guide-index-card-meta">
                  <span>{a.word_count}词 · {a.source}</span>
                </div>
              </div>
            </button>
          ))}
        </div>
      ) : (
        <div className="guide-index-grid">
          {readyPapers.length === 0 && <div className="guide-index-empty">还没有可阅读的原文</div>}
          {readyPapers.map(p => (
            <button key={p.id} className="guide-index-card" onClick={() => onOpenArticle('papers', p.id)}>
              <Cover title={p.filename?.replace(/\.pdf$/i, '') || p.filename} type="原文阅读" />
              <div className="guide-index-card-info">
                <div className="guide-index-card-title">{p.filename}</div>
                <div className="guide-index-card-meta">
                  <span>📄 原文阅读</span>
                </div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default GuideIndexPage;
