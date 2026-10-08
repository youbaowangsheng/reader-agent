import React, { useState, useEffect, lazy, Suspense } from 'react';
import { api } from '../api/client';

// 懒加载 PDF 面板（pdfjs-dist 较大，点击「看原文」才加载）
const GuidePdfPanel = lazy(() => import('../components/GuidePdfPanel'));

const NODE_ICON = { location: '📍', thought: '💡', question: '🤔', fig: '📊' };

function ReaderPage({ active }) {
  const [papers, setPapers] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [paperDetail, setPaperDetail] = useState(null);
  const [guide, setGuide] = useState(null);
  const [engagement, setEngagement] = useState({});
  const [pdfState, setPdfState] = useState(null); // {page, highlight}
  const [noteDraft, setNoteDraft] = useState({});
  const [myView, setMyView] = useState('');
  const [regenerating, setRegenerating] = useState(false);

  // 加载论文列表
  useEffect(() => {
    if (!active) return;
    api.getPapers().then(res => {
      setPapers(res.data);
      if (res.data.length > 0 && !selectedId) setSelectedId(res.data[0].id);
    }).catch(() => {});
  }, [active]);

  // 选中论文 → 加载详情 + 导读 + 交互
  useEffect(() => {
    if (!selectedId) return;
    setPaperDetail(null);
    setGuide(null);
    setEngagement({});
    setPdfState(null);
    setMyView('');
    setNoteDraft({});
    api.getPaper(selectedId).then(res => {
      const d = res.data;
      setPaperDetail(d);
      setGuide(d.reading_guide || null);
      setEngagement(d.user_engagement || {});
      setMyView(d.user_engagement?.my_view || '');
    }).catch(() => {});
  }, [selectedId]);

  // 触发生成导读（未生成时）
  useEffect(() => {
    if (!selectedId || !paperDetail) return;
    if (paperDetail.status !== 'ready') return;
    if (!guide) return;
    if (!guide.status || guide.status === 'none') {
      api.generateReadingGuide(selectedId).then(() => {
        setGuide(g => (g ? { ...g, status: 'generating' } : { status: 'generating' }));
      }).catch(() => {});
    }
  }, [guide, selectedId, paperDetail]);

  // 轮询导读生成状态
  useEffect(() => {
    if (!selectedId || !guide || guide.status !== 'generating') return;
    const timer = setInterval(async () => {
      try {
        const res = await api.getReadingGuide(selectedId);
        setGuide(res.data);
      } catch (_) {}
    }, 4000);
    return () => clearInterval(timer);
  }, [guide?.status, selectedId]);

  const saveEngagement = (patch) => {
    setEngagement(prev => {
      const next = { ...prev, ...patch };
      return next;
    });
    api.saveEngagement(selectedId, patch).catch(() => {});
  };

  const judge = (trailId, v) => {
    const judgments = { ...(engagement.judgments || {}) };
    if (judgments[trailId] === v) delete judgments[trailId]; // 再点取消
    else judgments[trailId] = v;
    saveEngagement({ judgments });
  };

  const note = (trailId, text) => {
    const notes = { ...(engagement.notes || {}), [trailId]: text };
    saveEngagement({ notes });
  };

  const submitMyView = () => saveEngagement({ my_view: myView });

  const answer = (qid, a) => {
    const quiz_answers = { ...(engagement.quiz_answers || {}), [qid]: a };
    saveEngagement({ quiz_answers });
  };

  const openPdf = (anchor) => {
    if (anchor?.page) setPdfState({ page: anchor.page, highlight: anchor.highlight || '' });
  };

  const regenerate = () => {
    setRegenerating(true);
    api.generateReadingGuide(selectedId, true).then(() => {
      setGuide(g => (g ? { ...g, status: 'generating' } : { status: 'generating' }));
    }).catch(() => {}).finally(() => setRegenerating(false));
  };

  const exportView = async () => {
    try {
      const res = await api.exportEngagement(selectedId);
      const blob = new Blob([res.data.markdown], { type: 'text/markdown;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = '我的阅读观点.md';
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      console.error('导出失败', e);
    }
  };

  const voice = (setter) => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { alert('当前浏览器不支持语音识别'); return; }
    const rec = new SR();
    rec.lang = 'zh-CN';
    rec.onresult = (e) => setter(e.results[0][0].transcript);
    rec.onerror = () => {};
    rec.start();
  };

  if (!active) return null;

  const fileUrl = paperDetail?.file_url ? paperDetail.file_url.replace(/^\.\//, '/') : '';
  const title = paperDetail?.paper_metadata?.title || paperDetail?.filename || '';
  const plan = guide?.reading_plan || {};
  const trail = guide?.trail || [];
  const verdict = guide?.verdict || {};
  const quiz = guide?.quiz || [];
  const status = guide?.status;

  return (
    <div className="guide-page">
      <div className="guide-toolbar">
        <select value={selectedId || ''} onChange={e => setSelectedId(e.target.value)}>
          <option value="">选择一篇论文…</option>
          {papers.map(p => <option key={p.id} value={p.id}>{p.filename}</option>)}
        </select>
        <div className="spacer" />
        {status === 'generated' && (
          <>
            <button className="btn-ghost" onClick={regenerate} disabled={regenerating}>
              {regenerating ? '重新生成中…' : '🔄 重新生成导读'}
            </button>
            <button className="btn-ghost" onClick={exportView}>📤 导出我的观点</button>
          </>
        )}
      </div>

      <div className={`guide-layout ${pdfState ? 'has-pdf' : ''}`}>
        <main className="guide-main">
          <div className="guide-paper-head">
            <div className="guide-tag">AI 导读</div>
            <h1>{title}</h1>
          </div>

          {status === 'generating' && (
            <div className="guide-status">🤖 AI 正在读这篇论文，生成导读中…</div>
          )}
          {status === 'error' && (
            <div className="guide-status err">导读生成失败：{guide?.error || '请重试'}</div>
          )}
          {!status && paperDetail?.status === 'ready' && (
            <div className="guide-status">论文已解析，正在准备导读…</div>
          )}
          {paperDetail && paperDetail.status !== 'ready' && (
            <div className="guide-status">{paperDetail.status === 'error' ? '解析失败' : '论文解析中，请稍候…'}</div>
          )}

          {status === 'generated' && (
            <>
              <SectionTitle label="阅读建议" />
              <ReadingPlan plan={plan} onLink={openPdf} />

              <SectionTitle label="一句话总结" />
              <div className="guide-summary"><p>{guide.summary}</p></div>

              <SectionTitle label="导读轨迹" />
              <div className="guide-trail">
                {trail.map(t => (
                  <TrailStop
                    key={t.id}
                    t={t}
                    judgment={engagement.judgments?.[t.id]}
                    note={engagement.notes?.[t.id]}
                    noteDraft={noteDraft[t.id] || ''}
                    onJudge={v => judge(t.id, v)}
                    onNote={text => note(t.id, text)}
                    onDraft={text => setNoteDraft(d => ({ ...d, [t.id]: text }))}
                    onLink={openPdf}
                    onVoice={voice}
                  />
                ))}
              </div>

              <SectionTitle label="整体判断" />
              <div className="guide-verdict">
                <p>{verdict.text}</p>
                <div className="guide-stars">
                  {'★'.repeat(verdict.stars || 0)}{'☆'.repeat(Math.max(0, 5 - (verdict.stars || 0)))}
                </div>
              </div>

              <SectionTitle label="我的观点" />
              <div className="guide-myview">
                <div className="guide-myview-prompt">读完了，别急着照单全收 —— 上面 AI 的观点你认同几条？哪些不同意？为什么？</div>
                <textarea
                  value={myView}
                  onChange={e => setMyView(e.target.value)}
                  placeholder="这篇论文我的看法是…"
                />
                <div className="guide-myview-actions">
                  <button className="guide-voice-btn" onClick={() => voice(setMyView)}>🎤 语音输入</button>
                  <button className="guide-submit" onClick={submitMyView}>记录我的观点</button>
                </div>
              </div>

              <SectionTitle label="检测题目" />
              <div className="guide-quiz">
                {quiz.map(q => (
                  <QuizItem
                    key={q.id}
                    q={q}
                    chosen={engagement.quiz_answers?.[q.id]}
                    onAnswer={a => answer(q.id, a)}
                  />
                ))}
              </div>
            </>
          )}
        </main>

        {pdfState && (
          <aside className="guide-pdf-aside">
            <Suspense fallback={<div className="guide-status">PDF 加载中…</div>}>
              <GuidePdfPanel
                fileUrl={fileUrl}
                page={pdfState.page}
                highlight={pdfState.highlight}
                onClose={() => setPdfState(null)}
              />
            </Suspense>
          </aside>
        )}
      </div>
    </div>
  );
}

function SectionTitle({ label }) {
  return (
    <div className="guide-sec-title">
      <div className="rule" /><span className="label">{label}</span><div className="rule" />
    </div>
  );
}

function ReadingPlan({ plan, onLink }) {
  const careful = plan.careful || [];
  const skim = plan.skim || [];
  const focus = plan.focus || [];
  return (
    <div className="guide-plan">
      {careful.length > 0 && (
        <div className="guide-plan-sec">
          <div className="guide-plan-h"><span className="guide-plan-tag careful">精读</span> 这 {careful.length} 处</div>
          <ul>
            {careful.map((c, i) => (
              <li key={i}>
                <span className="ref">{c.ref}</span>
                <span className="guide-link" onClick={() => onLink(c.anchor)}>
                  {c.label}{c.note ? ' —— ' + c.note : ''}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {skim.length > 0 && (
        <div className="guide-plan-sec">
          <div className="guide-plan-h"><span className="guide-plan-tag skim">略读</span> 扫一眼即可</div>
          <ul>
            {skim.map((c, i) => (
              <li key={i}>
                <span className="ref">{c.ref}</span>
                <span className="guide-link" onClick={() => onLink(c.anchor)}>{c.label}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {focus.length > 0 && (
        <div className="guide-plan-sec">
          <div className="guide-plan-h"><span className="guide-plan-tag focus">重点盯</span> 这 {focus.length} 点</div>
          <ul className="focus-list">
            {focus.map((f, i) => <li key={i}>{f}</li>)}
          </ul>
        </div>
      )}
    </div>
  );
}

function TrailStop({ t, judgment, note, noteDraft, onJudge, onNote, onDraft, onLink, onVoice }) {
  const [noteOpen, setNoteOpen] = useState(false);
  return (
    <div className="guide-stop">
      <div className="guide-stop-node">{NODE_ICON[t.type] || '📍'}</div>
      <div className="guide-stop-where">{t.where}</div>
      <div className="guide-stop-say">
        {t.says}
        {t.anchor?.page && (
          <div className="guide-stop-linkrow">
            <span className="guide-link" onClick={() => onLink(t.anchor)}>看原文 ↗</span>
          </div>
        )}
      </div>
      <div className="guide-react">
        <span className="guide-react-label">你的判断</span>
        <button className={`guide-jbtn agree ${judgment === 'agree' ? 'sel' : ''}`} onClick={() => onJudge('agree')}>✓ 认同</button>
        <button className={`guide-jbtn doubt ${judgment === 'doubt' ? 'sel' : ''}`} onClick={() => onJudge('doubt')}>? 存疑</button>
        <button className={`guide-jbtn reject ${judgment === 'reject' ? 'sel' : ''}`} onClick={() => onJudge('reject')}>✗ 不认同</button>
        <button className="guide-note-btn" onClick={() => setNoteOpen(o => !o)}>💬 说点什么</button>
      </div>
      {noteOpen && (
        <div className="guide-note-box">
          <input
            value={noteDraft || note || ''}
            onChange={e => onDraft(e.target.value)}
            onBlur={() => { if (noteDraft !== (note || '')) onNote(noteDraft); }}
            placeholder="写下你的看法…"
          />
          <button className="guide-mic" onClick={() => onVoice(text => onNote(text))} title="语音输入">🎤</button>
        </div>
      )}
    </div>
  );
}

function QuizItem({ q, chosen, onAnswer }) {
  const [revealed, setRevealed] = useState(false);
  return (
    <div className="guide-q">
      <div className="guide-q-t">{q.q}</div>
      <div className="guide-q-opts">
        {(q.options || []).map((opt, i) => {
          const letter = opt.split('.')[0].trim();
          const isChosen = chosen === letter;
          const isRight = letter === q.answer;
          return (
            <div
              key={i}
              className={`guide-opt ${isChosen ? (isRight ? 'right' : 'wrong') : ''} ${revealed && isRight ? 'right' : ''}`}
              onClick={() => { onAnswer(letter); setRevealed(true); }}
            >
              {opt}
            </div>
          );
        })}
      </div>
      {revealed && <div className="guide-q-explain">答案 {q.answer}。{q.explain}</div>}
    </div>
  );
}

export default ReaderPage;
