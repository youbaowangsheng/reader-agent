import React, { useState, useEffect, useRef } from 'react';
import { api } from '../api/client';

function ExtensivePage({ active }) {
  const [articles, setArticles] = useState([]);
  const [selected, setSelected] = useState(null);
  const [questions, setQuestions] = useState(null);
  const [generating, setGenerating] = useState(false);
  const [answers, setAnswers] = useState({});
  const [score, setScore] = useState(null);
  const [scoring, setScoring] = useState(false);
  const currentIdRef = useRef(null);

  useEffect(() => {
    if (active && articles.length === 0) {
      api.getExtensiveArticles().then(r => setArticles(r.data)).catch(() => {});
    }
  }, [active]);

  const selectArticle = (id) => {
    currentIdRef.current = id;
    setSelected(null); setQuestions(null); setAnswers({}); setScore(null);
    setGenerating(false); setScoring(false);
    api.getExtensiveArticle(id).then(r => {
      if (currentIdRef.current === id) setSelected(r.data);
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
      <div className={`intensive-list ${selected ? 'has-selection' : ''}`}>
        <div className="intensive-list-head">
          <span>新闻泛读</span>
          <span className="intensive-count">{articles.length} 篇</span>
        </div>
        {articles.map(a => (
          <button
            key={a.id}
            className={`intensive-item ${selected?.id === a.id ? 'active' : ''}`}
            onClick={() => selectArticle(a.id)}
          >
            <span className="intensive-title">{a.title}</span>
            <span className="intensive-meta"><span>{a.word_count}词</span><span>{a.source}</span></span>
          </button>
        ))}
      </div>

      <main className={`intensive-main ${selected ? 'has-selection' : ''}`}>
        {!selected ? (
          <div className="intensive-placeholder">← 选一篇新闻开始泛读</div>
        ) : (
          <>
            <div className="intensive-article-head">
              <h2>{selected.title}</h2>
              <div className="intensive-meta">
                <span>{selected.source} · {selected.word_count}词</span>
              </div>
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
