import React, { useState, useEffect } from 'react';
import { api } from '../api/client';

const LEVEL_COLOR = { L1: '#4caf50', L2: '#8bc34a', L3: '#ffb300', L4: '#ff7043', L5: '#e53935' };

function IntensivePage({ active }) {
  const [articles, setArticles] = useState([]);
  const [selected, setSelected] = useState(null);
  const [guide, setGuide] = useState(null);
  const [generating, setGenerating] = useState(false);
  const [summary, setSummary] = useState('');
  const [score, setScore] = useState(null);
  const [scoring, setScoring] = useState(false);

  useEffect(() => {
    if (active && articles.length === 0) {
      api.getIntensiveArticles().then(r => setArticles(r.data)).catch(() => {});
    }
  }, [active]);

  const selectArticle = (id) => {
    setSelected(null); setGuide(null); setScore(null); setSummary('');
    api.getIntensiveArticle(id).then(r => setSelected(r.data)).catch(() => {});
  };

  const genGuide = () => {
    if (!selected) return;
    setGenerating(true); setGuide(null); setScore(null);
    api.generateIntensiveGuide(selected.id).then(r => {
      setGuide(r.data); setGenerating(false);
    }).catch(() => setGenerating(false));
  };

  const submitSummary = () => {
    if (!summary.trim() || !guide?.writing_task) return;
    setScoring(true);
    api.scoreSummary(selected.id, guide.writing_task.key_points, summary).then(r => {
      setScore(r.data); setScoring(false);
    }).catch(() => setScoring(false));
  };

  if (!active) return null;

  return (
    <div className="intensive-page">
      {/* 左：文章列表 */}
      <aside className={`intensive-list ${selected ? 'has-selection' : ''}`}>
        <div className="intensive-list-head">
          <span>外刊精读</span>
          <span className="intensive-count">{articles.length} 篇</span>
        </div>
        {articles.length === 0 ? (
          <div className="intensive-empty">加载中…</div>
        ) : (
          articles.map(a => (
            <button
              key={a.id}
              className={`intensive-item ${selected?.id === a.id ? 'active' : ''}`}
              onClick={() => selectArticle(a.id)}
            >
              <span className="intensive-title">{a.title}</span>
              <span className="intensive-meta">
                <span className="intensive-level" style={{ background: LEVEL_COLOR[a.level] || '#999' }}>{a.level}</span>
                <span>{a.topic} · {a.word_count}词</span>
              </span>
            </button>
          ))
        )}
      </aside>

      {/* 右：内容 */}
      <main className={`intensive-main ${selected ? 'has-selection' : ''}`}>
        {!selected ? (
          <div className="intensive-placeholder">← 选一篇外刊开始精读</div>
        ) : (
          <>
            <div className="intensive-article-head">
              <h2>{selected.title}</h2>
              <div className="intensive-meta">
                <span className="intensive-level" style={{ background: LEVEL_COLOR[selected.level] || '#999' }}>{selected.level}</span>
                <span>{selected.topic} · {selected.word_count}词</span>
              </div>
              <button className="intensive-gen-btn" onClick={genGuide} disabled={generating}>
                {generating ? '🤖 AI 带读生成中…' : guide ? '🔄 重新生成带读' : '🤖 AI 带读'}
              </button>
            </div>

            {!guide && !generating && (
              <div className="intensive-hint">点「AI 带读」，AI 会逐段带你精读这篇文章（生词 / 长难句 / 背景 / 观点），读完后做概要写作。</div>
            )}

            {guide && (
              <div className="intensive-guide">
                <div className="intensive-overview">
                  <div className="intensive-sec-title">📖 一句话概述</div>
                  <p>{guide.overview}</p>
                </div>

                <div className="intensive-sec-title">📚 逐段带读</div>
                {(guide.paragraphs || []).map(p => (
                  <div className="intensive-para" key={p.idx}>
                    <div className="intensive-para-tag">第 {p.idx} 段</div>

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
