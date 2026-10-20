import React, { useState, useEffect, useRef, useCallback } from 'react';
import { api } from '../api/client';
import { Thumb } from '../components/Cover';

const LEVEL_COLOR = { L1: '#4caf50', L2: '#8bc34a', L3: '#ffb300', L4: '#ff7043', L5: '#e53935' };

function IntensivePage({ active, openArticle }) {
  const [articles, setArticles] = useState([]);
  const [selected, setSelected] = useState(null);
  const [guide, setGuide] = useState(null);
  const [generating, setGenerating] = useState(false);
  const [summary, setSummary] = useState('');
  const [score, setScore] = useState(null);
  const [scoring, setScoring] = useState(false);
  const [guideCache, setGuideCache] = useState({});
  const [generatingIds, setGeneratingIds] = useState({});
  const currentIdRef = useRef(null);
  const [listCollapsed, setListCollapsed] = useState(false);
  const [readMap, setReadMap] = useState({});
  const [hasMore, setHasMore] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const listRef = useRef(null);

  const loadArticles = useCallback((offset, append) => {
    api.getIntensiveArticles({ limit: 20, offset }).then(r => {
      const data = r.data || [];
      if (append) setArticles(prev => [...prev, ...data]);
      else setArticles(data);
      setHasMore(data.length === 20);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (active && articles.length === 0) {
      loadArticles(0, false);
    }
  }, [active, loadArticles]);

  // 列表滚动到底部加载下一页
  const onScroll = () => {
    const el = listRef.current;
    if (!el || !hasMore || loadingMore) return;
    if (el.scrollTop + el.clientHeight >= el.scrollHeight - 120) {
      setLoadingMore(true);
      loadArticles(articles.length, true);
      setTimeout(() => setLoadingMore(false), 300);
    }
  };

  // 加载已读记录（用于"标记读完"状态）
  useEffect(() => {
    if (active) {
      api.getReadLog().then(r => {
        const m = {};
        (r.data?.read || []).forEach(e => { m[`${e.type}:${e.id}`] = true; });
        setReadMap(m);
      }).catch(() => {});
    }
  }, [active]);

  // 从导读目录页跳转过来时，打开指定文章
  useEffect(() => {
    if (active && openArticle && openArticle.id != null) {
      selectArticle(openArticle.id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [openArticle]);

  const selectArticle = (id) => {
    currentIdRef.current = id;
    setSelected(null);
    setGuide(guideCache[id] || null);
    setGenerating(!!generatingIds[id]);
    setScore(null); setSummary('');
    setScoring(false);
    api.getIntensiveArticle(id).then(r => {
      if (currentIdRef.current === id) setSelected(r.data);
    }).catch(() => {});
    // 自动加载已生成的导读（持久化，下次直接看，不重新生成）
    if (!guideCache[id]) {
      api.getIntensiveGuide(id).then(r => {
        if (currentIdRef.current === id && r.data) {
          setGuide(r.data);
          setGuideCache(c => ({ ...c, [id]: r.data }));
        }
      }).catch(() => {});
    }
  };

  const markRead = () => {
    if (!selected) return;
    api.markRead('intensive', selected.id).then(() => {
      setReadMap(m => ({ ...m, [`intensive:${selected.id}`]: true }));
    }).catch(() => {});
  };

  const genGuide = () => {
    if (!selected) return;
    const id = selected.id;
    setGeneratingIds(g => ({ ...g, [id]: true }));
    setGenerating(true); setGuide(null); setScore(null);
    api.generateIntensiveGuide(id).then(r => {
      if (r.data && !r.data.error) setGuideCache(c => ({ ...c, [id]: r.data }));
      setGeneratingIds(g => { const n = { ...g }; delete n[id]; return n; });
      if (currentIdRef.current === id) { setGuide(r.data); setGenerating(false); }
    }).catch(() => {
      setGeneratingIds(g => { const n = { ...g }; delete n[id]; return n; });
      if (currentIdRef.current === id) setGenerating(false);
    });
  };

  const submitSummary = () => {
    if (!summary.trim() || !guide?.writing_task) return;
    const id = selected.id;
    setScoring(true);
    api.scoreSummary(id, guide.writing_task.key_points, summary).then(r => {
      if (currentIdRef.current === id) { setScore(r.data); setScoring(false); }
    }).catch(() => {
      if (currentIdRef.current === id) setScoring(false);
    });
  };

  if (!active) return null;

  return (
    <div className="intensive-page">
      {/* 左：文章列表 */}
      <aside ref={listRef} onScroll={onScroll} className={`intensive-list ${selected ? 'has-selection' : ''} ${listCollapsed ? 'collapsed' : ''}`}>
        <div className="intensive-list-head">
          {listCollapsed ? (
            <button className="side-toggle" onClick={() => setListCollapsed(false)} title="展开列表">»</button>
          ) : (
            <>
              <span>外刊精读</span>
              <span className="intensive-count">{articles.length} 篇</span>
              <button className="side-toggle" onClick={() => setListCollapsed(true)} title="收起列表">«</button>
            </>
          )}
        </div>
        {!listCollapsed && (articles.length === 0 ? (
          <div className="intensive-empty">加载中…</div>
        ) : (
          <>
          {articles.map(a => (
            <button
              key={a.id}
              className={`intensive-item ${selected?.id === a.id ? 'active' : ''}`}
              onClick={() => selectArticle(a.id)}
            >
              <Thumb title={a.title} keyword={a.topic} size="sm" />
              <span className="intensive-item-body">
                <span className="intensive-title">{a.title}</span>
                {a.created_at && (Date.now() - new Date(a.created_at).getTime()) < 7 * 24 * 3600 * 1000 && (
                  <span className="new-badge">新</span>
                )}
                <span className="intensive-meta">
                  <span className="intensive-level" style={{ background: LEVEL_COLOR[a.level] || '#999' }}>{a.level}</span>
                  <span>{a.topic} · {a.word_count}词</span>
                </span>
              </span>
            </button>
          ))}
          {articles.length > 0 && (
            <div className="list-more">{loadingMore ? '加载中…' : hasMore ? '向下滚动加载更多' : '已全部加载'}</div>
          )}
          </>
        ))}
      </aside>

      {/* 右：内容 */}
      <main className={`intensive-main ${selected ? 'has-selection' : ''}`}>
        {!selected ? (
          <div className="intensive-placeholder">← 选一篇外刊开始精读</div>
        ) : (
          <>
            <button className="mobile-back" onClick={() => setSelected(null)}>← 返回列表</button>
            <div className="intensive-article-head">
              <h2>{selected.title}</h2>
              <div className="intensive-meta">
                <span className="intensive-level" style={{ background: LEVEL_COLOR[selected.level] || '#999' }}>{selected.level}</span>
                <span>{selected.topic} · {selected.word_count}词</span>
              </div>
              <button className={`mark-read-btn ${readMap[`intensive:${selected.id}`] ? 'done' : ''}`} onClick={markRead}>
                {readMap[`intensive:${selected.id}`] ? '✓ 已读完' : '标记读完'}
              </button>
            </div>

            <button className="intensive-gen-btn" onClick={genGuide} disabled={generating}>
              {generating ? '🤖 AI 正在逐段导读…' : guide ? '🔄 重新生成导读' : '🤖 AI 导读'}
            </button>

            {!guide && !generating && (
              <div className="intensive-hint">点「AI 导读」，AI 会逐段带你精读这篇文章（生词 / 长难句 / 背景 / 观点），读完后做概要写作。</div>
            )}

            {guide && (
              <div className="intensive-guide">
                <div className="intensive-overview">
                  <div className="intensive-sec-title">📖 一句话概述</div>
                  <p>{guide.overview}</p>
                </div>

                <div className="intensive-sec-title">📚 逐段导读</div>
                {(guide.paragraphs || []).map(p => (
                  <div className="intensive-para" key={p.idx}>
                    <div className="intensive-para-tag">第 {p.idx} 段</div>

                    {p.text && (
                      <div className="intensive-para-text">{p.text}</div>
                    )}

                    {(p.vocab || []).length > 0 && (
                      <div className="intensive-vocab">
                        {p.vocab.map((v, i) => (
                          <div className="intensive-vocab-item" key={i}>
                            <span className="intensive-word">{v.word}</span>
                            <span className="intensive-ipa">{v.ipa}</span>
                            <span className="intensive-pos">{v.pos}</span>
                            <span className="intensive-meaning">{v.meaning}</span>
                            <span className="intensive-example">{v.example}</span>
                          </div>
                        ))}
                      </div>
                    )}

                    {(p.long_sentences || []).length > 0 && (
                      <div className="intensive-sent">
                        {p.long_sentences.map((s, i) => (
                          <div className="intensive-sent-item" key={i}>
                            <div className="intensive-sent-text">「{s.text}」</div>
                            <div className="intensive-sent-analysis">🔍 {s.analysis}</div>
                          </div>
                        ))}
                      </div>
                    )}

                    {p.context && (
                      <div className="intensive-context">🌏 背景：{p.context}</div>
                    )}

                    {p.idea && (
                      <div className="intensive-idea">💡 本段观点：{p.idea}</div>
                    )}
                  </div>
                ))}

                {/* 概要写作 */}
                <div className="intensive-writing">
                  <div className="intensive-sec-title">✍️ 概要写作</div>
                  <div className="intensive-writing-instruction">{guide.writing_task?.instruction}</div>
                  <textarea
                    className="intensive-textarea"
                    value={summary}
                    onChange={e => setSummary(e.target.value)}
                    placeholder="用英文写下你的概要…"
                    rows={5}
                  />
                  <div className="intensive-writing-actions">
                    <button className="intensive-submit" onClick={submitSummary} disabled={scoring || !summary.trim()}>
                      {scoring ? '评分中…' : '提交评分'}
                    </button>
                  </div>

                  {score && (
                    <div className="intensive-score">
                      <div className="intensive-score-total">
                        <span className="intensive-score-num">{score.score}</span>
                        <span className="intensive-score-label">总分</span>
                      </div>
                      <div className="intensive-score-dims">
                        <span>要点覆盖 {score.coverage}</span>
                        <span>语言 {score.language}</span>
                        <span>连贯 {score.coherence}</span>
                      </div>
                      <div className="intensive-score-comment">{score.comment}</div>
                      {(score.suggestions || []).length > 0 && (
                        <ul className="intensive-suggestions">
                          {score.suggestions.map((s, i) => <li key={i}>{s}</li>)}
                        </ul>
                      )}
                    </div>
                  )}
                </div>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}

export default IntensivePage;
