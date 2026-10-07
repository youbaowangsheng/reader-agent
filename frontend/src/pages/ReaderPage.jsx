import React, { useState, useEffect, useRef } from 'react';
import { api } from '../api/client';

function ReaderPage({ active }) {
  const [papers, setPapers] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [paperDetail, setPaperDetail] = useState(null);
  const [notes, setNotes] = useState(null);
  const [factCards, setFactCards] = useState([]);
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState('');
  const [loading, setLoading] = useState(false);
  const [activeAsstTab, setActiveAsstTab] = useState('chat');
  const [conceptIndex, setConceptIndex] = useState(0);
  const [selectedText, setSelectedText] = useState('');
  const [sessionId] = useState(() => localStorage.getItem('reader_session') || crypto.randomUUID());
  const bodyRef = useRef(null);

  useEffect(() => {
    localStorage.setItem('reader_session', sessionId);
  }, [sessionId]);

  // 加载论文列表
  useEffect(() => {
    if (!active) return;
    api.getPapers().then(res => {
      setPapers(res.data);
      if (res.data.length > 0 && !selectedId) {
        setSelectedId(res.data[0].id);
      }
    }).catch(() => {});
  }, [active]);

  // 选中论文 → 加载详情 + 笔记 + 事实卡片
  useEffect(() => {
    if (!selectedId) return;
    setPaperDetail(null);
    setNotes(null);
    setFactCards([]);
    setMessages([]);
    setConceptIndex(0);
    setSelectedText('');
    api.getPaper(selectedId).then(res => setPaperDetail(res.data)).catch(() => {});
    api.getNotes(selectedId).then(res => setNotes(res.data)).catch(() => setNotes(null));
    api.getFactCards(selectedId).then(res => setFactCards(res.data)).catch(() => {});
  }, [selectedId]);

  // 划词
  const handleMouseUp = () => {
    const sel = window.getSelection();
    const t = sel ? sel.toString().trim() : '';
    if (t && t.length < 500) setSelectedText(t);
  };

  const handleAsk = async (q) => {
    const text = (q ?? question).trim();
    if (!text || !selectedId || loading) return;
    setMessages(prev => [...prev, { role: 'user', content: text }]);
    setQuestion('');
    setLoading(true);
    try {
      const history = messages.map(m => ({ role: m.role, content: m.content }));
      const res = await api.askQuestion(selectedId, text, sessionId, history);
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: res.data.answer,
        citations: res.data.citations || []
      }]);
    } catch (err) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: '回答失败：' + (err.response?.data?.detail || err.message)
      }]);
    } finally {
      setLoading(false);
    }
  };

  const sections = paperDetail?.parsed_structure?.sections || [];
  const title = paperDetail?.parsed_structure?.title || paperDetail?.filename || '';
  const keyConcepts = notes?.key_concepts || [];
  const status = paperDetail?.status || '';

  const scrollToSection = (idx) => {
    const el = document.getElementById(`sec-${idx}`);
    if (el && bodyRef.current) {
      bodyRef.current.scrollTo({ top: el.offsetTop - 16, behavior: 'smooth' });
    }
  };

  if (!active) return null;

  return (
    <div className="reader-page">
      <div className="reader-toolbar">
        <select value={selectedId || ''} onChange={e => setSelectedId(e.target.value)}>
          <option value="">选择一篇论文…</option>
          {papers.map(p => (
            <option key={p.id} value={p.id}>{p.filename} · {p.status}</option>
          ))}
        </select>
        <div className="spacer" />
        <button className="btn-ghost">导出笔记</button>
      </div>

      <div className="reader-layout">
        {/* 左栏：目录 */}
        <aside className="r-sidebar">
          <div className="r-group">
            <div className="r-label">目录</div>
            {sections.length === 0 ? (
              <div className="empty-state">暂无内容</div>
            ) : sections.map((s, i) => (
              <button
                key={i}
                className={`r-toc-item ${s.level > 1 ? 'child' : ''}`}
                onClick={() => scrollToSection(i)}
              >
                {s.level <= 1 && <span className="num">{i + 1}</span>}
                <span>{s.heading}</span>
              </button>
            ))}
          </div>
        </aside>

        {/* 中栏：正文 */}
        <main className="r-body" ref={bodyRef} onMouseUp={handleMouseUp}>
          {paperDetail ? (
            status === 'ready' && sections.length > 0 ? (
              <article className="paper">
                <h1>{title}</h1>
                {sections.map((s, i) => (
                  <section key={i} id={`sec-${i}`}>
                    {s.level <= 1 ? <h2>{s.heading}</h2> : <h3>{s.heading}</h3>}
                    <p>{s.content}</p>
                  </section>
                ))}
              </article>
            ) : (
              <div className="reader-empty">
                <div className="icon">…</div>
                <div>{status === 'error' ? ('解析失败：' + (paperDetail.error_message || '')) : '论文解析中，请稍候…'}</div>
              </div>
            )
          ) : (
            <div className="reader-empty">
              <div className="icon">📄</div>
              <div>选择一篇论文开始阅读</div>
            </div>
          )}
        </main>

        {/* 右栏：AI 助读 */}
        <aside className="r-asst">
          <div className="asst-head">
            <div className="t"><span className="dot"></span> AI 助读</div>
            <div className="sub">术语解释 · 段落问答 · 笔记</div>
          </div>

          {keyConcepts.length > 0 ? (
            <div className="term-card">
              <div className="label">核心概念</div>
              <div className="term-name">{keyConcepts[conceptIndex].term}</div>
              <div className="term-def">{keyConcepts[conceptIndex].definition}</div>
              <div className="chips" style={{ marginTop: 8 }}>
                {keyConcepts.map((c, i) => (
                  <button
                    key={i}
                    className={`chip ${i === conceptIndex ? 'active' : ''}`}
                    onClick={() => setConceptIndex(i)}
                  >{c.term}</button>
                ))}
              </div>
            </div>
          ) : (
            <div className="term-card">
              <div className="label">核心概念</div>
              <div className="term-def" style={{ color: 'var(--text-4)' }}>暂无，解析完成后自动生成</div>
            </div>
          )}

          <div className="asst-tabs">
            <button className={`asst-tab ${activeAsstTab === 'chat' ? 'active' : ''}`} onClick={() => setActiveAsstTab('chat')}>对话</button>
            <button className={`asst-tab ${activeAsstTab === 'notes' ? 'active' : ''}`} onClick={() => setActiveAsstTab('notes')}>笔记</button>
            <button className={`asst-tab ${activeAsstTab === 'cards' ? 'active' : ''}`} onClick={() => setActiveAsstTab('cards')}>卡片</button>
          </div>

          <div className="asst-body">
            {activeAsstTab === 'chat' && (
              <>
                <div className="chips">
                  <button className="chip" onClick={() => handleAsk('这篇文章的主要贡献是什么？')}>主要贡献</button>
                  <button className="chip" onClick={() => handleAsk('用中文总结这篇论文')}>总结</button>
                  <button className="chip" onClick={() => handleAsk('这篇论文的方法有什么局限性？')}>局限性</button>
                </div>
                {messages.length === 0 && (
                  <div className="empty-state">针对论文提问，AI 会带页码引用回答</div>
                )}
                {messages.map((m, i) => (
                  <div key={i} className={`msg ${m.role === 'user' ? 'user' : 'ai'}`}>
                    <div className="who">{m.role === 'user' ? '你' : 'AI 助读'}</div>
                    <div className="bubble">
                      {m.content}
                      {m.citations?.map((c, j) => (
                        <span key={j} className="citation">
                          「{(c.quote || '').slice(0, 60)}」 {c.heading} · p.{c.page_range}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </>
            )}

            {activeAsstTab === 'notes' && (
              notes ? (
                <>
                  {notes.summary && (
                    <div className="ai-summary">
                      <div className="label">摘要</div>
                      <div className="content">{notes.summary}</div>
                    </div>
                  )}
                  {notes.critical_questions?.length > 0 && (
                    <div>
                      <div className="r-label">批判性思考</div>
                      {notes.critical_questions.map((q, i) => (
                        <div key={i} className="crit-q">{q}</div>
                      ))}
                    </div>
                  )}
                  {notes.overall_evaluation && (
                    <div className="ai-summary">
                      <div className="label">综合评价</div>
                      <div className="content">
                        创新 {notes.overall_evaluation.novelty} · 严谨 {notes.overall_evaluation.rigor} · 可复现 {notes.overall_evaluation.reproducibility}
                      </div>
                    </div>
                  )}
                </>
              ) : (
                <div className="empty-state">暂无笔记</div>
              )
            )}

            {activeAsstTab === 'cards' && (
              factCards.length > 0 ? factCards.map((c, i) => (
                <div key={i} className="fact-card">
                  <div className="claim">
                    <span className={`conf-dot ${c.confidence >= 0.7 ? 'conf-high' : c.confidence >= 0.4 ? 'conf-mid' : 'conf-low'}`}></span>
                    {c.claim}
                  </div>
                  {c.evidence && <div className="evidence-preview">{c.evidence}</div>}
                </div>
              )) : (
                <div className="empty-state">暂无事实卡片</div>
              )
            )}
          </div>

          {selectedText && (
            <div style={{ padding: '6px 12px 0' }}>
              <button className="chip" onClick={() => handleAsk('请解释下面这段：' + selectedText)}>
                问 AI：「{selectedText.slice(0, 26)}…」
              </button>
            </div>
          )}

          <div className="asst-input">
            <div className="input-row">
              <textarea
                value={question}
                onChange={e => setQuestion(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleAsk(); } }}
                placeholder="针对当前论文提问…（Enter 发送）"
              />
              <button className="send-btn" onClick={() => handleAsk()} disabled={loading || !question.trim()}>→</button>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}

export default ReaderPage;
