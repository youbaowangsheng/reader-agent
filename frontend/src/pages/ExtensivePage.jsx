import React, { useState, useEffect, useRef, useCallback } from 'react';
import { api } from '../api/client';

function ExtensivePage({ active, openArticle }) {
  const [articles, setArticles] = useState([]);
  const [selected, setSelected] = useState(null);
  const [questions, setQuestions] = useState(null);
  const [generating, setGenerating] = useState(false);
  const [answers, setAnswers] = useState({});
  const [score, setScore] = useState(null);
  const [scoring, setScoring] = useState(false);
  const currentIdRef = useRef(null);
  const [listCollapsed, setListCollapsed] = useState(false);
  const [readMap, setReadMap] = useState({});
  const [hasMore, setHasMore] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const listRef = useRef(null);

  const loadArticles = useCallback((offset, append) => {
    api.getExtensiveArticles({ limit: 20, offset }).then(r => {
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
    setSelected(null); setQuestions(null); setAnswers({}); setScore(null);
    setGenerating(false); setScoring(false);
    api.getExtensiveArticle(id).then(r => {
      if (currentIdRef.current === id) setSelected(r.data);
    }).catch(() => {});
    // 自动加载已生成的大意检测题（持久化，下次直接看）
    api.getExtensiveQuestions(id).then(r => {
      if (currentIdRef.current === id && r.data) setQuestions(r.data);
    }).catch(() => {});
  };

  const markRead = () => {
    if (!selected) return;
    api.markRead('extensive', selected.id).then(() => {
      setReadMap(m => ({ ...m, [`extensive:${selected.id}`]: true }));
    }).catch(() => {});
  };

  const genQuestions = () => {
    if (!selected) return;
    const id = selected.id;
    setGenerating(true); setQuestions(null); setScore(null);
    api.generateExtensiveQuestions(id).then(r => {
      if (currentIdRef.current === id) { setQuestions(r.data); setGenerating(false); }
    }).catch(() => {
      if (currentIdRef.current === id) setGenerating(false);
    });
  };

  const submit = () => {
    if (!selected || !questions) return;
    const id = selected.id;
    setScoring(true);
    api.scoreExtensive(id, questions.questions || [], answers).then(r => {
      if (currentIdRef.current === id) { setScore(r.data); setScoring(false); }
    }).catch(() => {
      if (currentIdRef.current === id) setScoring(false);
    });
  };

  if (!active) return null;

  return (
    <div className="intensive-page">
      <div ref={listRef} onScroll={onScroll} className={`intensive-list ${selected ? 'has-selection' : ''} ${listCollapsed ? 'collapsed' : ''}`}>
        <div className="intensive-list-head">
          {listCollapsed ? (
            <button className="side-toggle" onClick={() => setListCollapsed(false)} title="展开列表">»</button>
          ) : (
            <>
              <span>新闻泛读</span>
              <span className="intensive-count">{articles.length} 篇</span>
              <button className="side-toggle" onClick={() => setListCollapsed(true)} title="收起列表">«</button>
            </>
          )}
        </div>
        {!listCollapsed && articles.map(a => (
          <button
            key={a.id}
            className={`intensive-item ${selected?.id === a.id ? 'active' : ''}`}
            onClick={() => selectArticle(a.id)}
          >
            <span className="intensive-title">{a.title}</span>
            {a.created_at && (Date.now() - new Date(a.created_at).getTime()) < 7 * 24 * 3600 * 1000 && (
              <span className="new-badge">NEW</span>
            )}
            <span className="intensive-meta"><span>{a.word_count}词</span><span>{a.source}</span></span>
          </button>
        ))}
        {!listCollapsed && articles.length > 0 && (
          <div className="list-more">{loadingMore ? '加载中…' : hasMore ? '向下滚动加载更多' : '已全部加载'}</div>
        )}
      </div>

      <main className={`intensive-main ${selected ? 'has-selection' : ''}`}>
        {!selected ? (
          <div className="intensive-placeholder">← 选一篇新闻开始泛读</div>
        ) : (
          <>
            <button className="mobile-back" onClick={() => setSelected(null)}>← 返回列表</button>
            <div className="intensive-article-head">
              <h2>{selected.title}</h2>
              <div className="intensive-meta">
                <span>{selected.source} · {selected.word_count}词</span>
              </div>
              <button className={`mark-read-btn ${readMap[`extensive:${selected.id}`] ? 'done' : ''}`} onClick={markRead}>
                {readMap[`extensive:${selected.id}`] ? '✓ 已读完' : '标记读完'}
              </button>
            </div>

            <div className="intensive-sec-title">📄 全文</div>
            <div className="intensive-passage">{selected.body}</div>

            <button className="intensive-gen-btn" onClick={genQuestions} disabled={generating}>
              {generating ? '🤖 出题中…' : questions ? '🔄 重新出题' : '🤖 大意检测'}
            </button>

            {!questions && !generating && (
              <div className="intensive-hint">先快速读完全文，点「大意检测」，AI 会出 2-3 道题考你抓没抓住文章大意。</div>
            )}

            {questions && (questions.questions || []).map((q, i) => (
              <div className="intensive-ext-q" key={i}>
                <div className="intensive-ext-q-text">{q.q}</div>
                <textarea
                  className="intensive-textarea"
                  value={answers[i] || ''}
                  onChange={e => setAnswers(a => ({ ...a, [i]: e.target.value }))}
                  placeholder="用英文回答…"
                  rows={3}
                />
              </div>
            ))}

            {questions && (
              <div className="intensive-writing-actions">
                <button className="intensive-submit" onClick={submit} disabled={scoring}>
                  {scoring ? '评分中…' : '提交'}
                </button>
              </div>
            )}

            {score && (
              <div className="intensive-score">
                <div className="intensive-score-comment">{score.overall}</div>
                {(score.results || []).map((r, i) => (
                  <div className="intensive-ext-result" key={i}>
                    <div className={`intensive-ext-verdict ${r.correct ? 'ok' : 'no'}`}>
                      {r.correct ? '✓ 正确' : '✗ 有偏差'}：{r.q}
                    </div>
                    <div className="intensive-ext-reference">参考：{r.reference}</div>
                    <div className="intensive-ext-feedback">{r.feedback}</div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}

export default ExtensivePage;
