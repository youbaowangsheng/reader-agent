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
  const [level, setLevel] = useState(3);
  const [stats, setStats] = useState({ topics: {}, days_since: null });

  useEffect(() => {
    if (active) {
      setLoading(true);
      Promise.all([
        api.getIntensiveArticles(),
        api.getExtensiveArticles(),
        api.getPapers(),
        api.getLevel(),
        api.getStats(),
      ]).then(([ir, er, pr, lr, sr]) => {
        setIntensive(ir.data || []);
        setExtensive(er.data || []);
        setPapers(pr.data || []);
        setLevel(lr.data?.level || 3);
        setStats(sr.data || { topics: {}, days_since: null });
        setLoading(false);
      }).catch(() => setLoading(false));
    }
  }, [active]);

  if (!active) return null;

  const readyPapers = papers.filter(p => p.status === 'ready');

  // 今天该读：优先泛读；断读(>=3天)推最短泛读轻量启动；精读按难度+兴趣匹配
  const targetLevel = `L${level}`;
  const topicRank = stats.topics || {};
  const pickIntensive = () => {
    const levelMatches = intensive.filter(a => a.level === targetLevel);
    const pool = levelMatches.length ? levelMatches : intensive;
    const sorted = [...pool].sort((a, b) => (topicRank[b.topic] || 0) - (topicRank[a.topic] || 0));
    return sorted[0] || intensive[0];
  };
  const stale = stats.days_since != null && stats.days_since >= 3;
  let todayArticle, todayType;
  if (stale && extensive.length) {
    todayArticle = [...extensive].sort((a, b) => a.word_count - b.word_count)[0];
    todayType = 'extensive';
  } else {
    todayArticle = extensive[0] || pickIntensive() || null;
    todayType = extensive[0] ? 'extensive' : 'intensive';
  }

  return (
    <div className="guide-index">
      <div className="guide-index-head">
        <h2>📖 首页</h2>
        <p>每天读一篇，把阅读坚持下去</p>
      </div>

      {!loading && todayArticle && (
        <div className="today-card" onClick={() => onOpenArticle(todayType, todayArticle.id)}>
          <div className="today-cover">
            <Cover title={todayArticle.title} type={todayType === 'extensive' ? '今日泛读' : '今日精读'} subtitle={todayArticle.source || todayArticle.topic || ''} />
          </div>
          <div className="today-info">
            <div className="today-label">{stale ? '🎯 回来啦，先读一篇轻松的' : '🎯 今天该读'}</div>
            <div className="today-title">{todayArticle.title}</div>
            <div className="today-meta">
              {todayType === 'extensive'
                ? `${todayArticle.word_count}词 · ${todayArticle.source} · 约10分钟`
                : `${todayArticle.topic} · ${todayArticle.word_count}词 · 约35分钟`}
            </div>
            <div className="today-btn">开始读 →</div>
          </div>
        </div>
      )}

      <div className="guide-index-section-title">📚 全部文章</div>

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
