import React, { useState, useEffect, lazy, Suspense } from 'react';
import { api } from '../api/client';

const GuidePdfPanel = lazy(() => import('../components/GuidePdfPanel'));

// 原文列表模块级缓存（切换 tab 秒出）
let _papersCache = null;

function ReaderPage({ active, openPaperId }) {
  const [papers, setPapers] = useState([]);
  const [papersLoading, setPapersLoading] = useState(true);
  const [selectedId, setSelectedId] = useState(null);
  const [paperDetail, setPaperDetail] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [listCollapsed, setListCollapsed] = useState(false);
  const [tocCollapsed, setTocCollapsed] = useState(false);
  const [readMap, setReadMap] = useState({});

  // 加载原文列表
  useEffect(() => {
    if (!active) return;
    if (_papersCache) {
      setPapers(_papersCache);
      setPapersLoading(false);
      return;
    }
    setPapersLoading(true);
    api.getPapers().then(res => {
      _papersCache = res.data;
      setPapers(res.data);
    }).catch(() => {}).finally(() => setPapersLoading(false));
  }, [active]);

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

  // 从首页导读跳转过来时，打开指定原文
  useEffect(() => {
    if (active && openPaperId && openPaperId.id != null) {
      setSelectedId(openPaperId.id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [openPaperId]);

  // 有解析中的原文时，轮询刷新状态
  useEffect(() => {
    if (!active) return;
    const hasProcessing = papers.some(p => p.status === 'pending' || p.status === 'processing' || p.status === 'parsed');
    if (!hasProcessing) return;
    const timer = setInterval(() => {
      api.getPapers().then(r => { _papersCache = r.data; setPapers(r.data); }).catch(() => {});
    }, 4000);
    return () => clearInterval(timer);
  }, [active, papers]);

  // 选中原文 → 加载详情（含目录 parsed_structure.sections）
  useEffect(() => {
    if (!selectedId) return;
    setPaperDetail(null);
    setCurrentPage(1);
    api.getPaper(selectedId).then(res => setPaperDetail(res.data)).catch(() => {});
  }, [selectedId]);

  // 上传原文 → 自动解析 → 刷新列表
  const handleUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const res = await api.uploadPaper(file);
      _papersCache = null;
      api.getPapers().then(r => { _papersCache = r.data; setPapers(r.data); }).catch(() => {});
      if (res.data?.id) api.parsePaper(res.data.id).catch(() => {});
    } catch (err) {
      alert('上传失败：' + (err.response?.data?.detail || err.message));
    } finally {
      setUploading(false);
      e.target.value = '';
    }
  };

  const markRead = () => {
    if (!selectedId) return;
    api.markRead('paper', selectedId).then(() => {
      setReadMap(m => ({ ...m, [`paper:${selectedId}`]: true }));
    }).catch(() => {});
  };

  if (!active) return null;

  const fileUrl = paperDetail?.file_url ? paperDetail.file_url.replace(/^\.\//, '/') : '';
  const sections = paperDetail?.parsed_structure?.sections || [];

  const jumpTo = (pageRange) => {
    const m = String(pageRange || '').match(/\d+/);
    if (m) setCurrentPage(parseInt(m[0], 10));
  };

  return (
    <div className="intensive-page paper-page">
      {/* 左：原文列表 */}
      <aside className={`intensive-list paper-list ${listCollapsed ? 'collapsed' : ''}`}>
        <div className="intensive-list-head">
          {listCollapsed ? (
            <button className="side-toggle" onClick={() => setListCollapsed(false)} title="展开列表">»</button>
          ) : (
            <>
              <span>原文列表</span>
              <span className="intensive-count">{papers.length} 篇</span>
              <button className="side-toggle" onClick={() => setListCollapsed(true)} title="收起列表">«</button>
            </>
          )}
        </div>
        {!listCollapsed && (
          <>
        <div className="paper-upload">
          <label className="paper-upload-label">
            {uploading ? '上传中…' : '📄 上传 PDF'}
            <input type="file" accept=".pdf,.epub" onChange={handleUpload} disabled={uploading} style={{ display: 'none' }} />
          </label>
        </div>
        {papersLoading ? (
          <div className="intensive-empty">加载中…</div>
        ) : papers.length === 0 ? (
          <div className="intensive-empty">还没有原文，点上面上传 PDF</div>
        ) : (
          papers.map(p => (
            <button
              key={p.id}
              className={`intensive-item ${p.id === selectedId ? 'active' : ''}`}
              onClick={() => p.status === 'ready' && setSelectedId(p.id)}
              disabled={p.status !== 'ready'}
              title={p.filename}
            >
              <span className="intensive-title">{p.filename}</span>
              <span className="intensive-meta">
                <span>{p.status === 'ready' ? '可阅读' : p.status === 'processing' ? '解析中…' : p.status === 'parsed' ? '准备中…' : p.status === 'error' ? '失败' : '待解析'}</span>
              </span>
            </button>
          ))
        )}
          </>
        )}
      </aside>

      {/* 右：目录 + PDF 原文 */}
      <main className="intensive-main paper-main">
        {!selectedId ? (
          <div className="intensive-placeholder">← 选一篇原文开始阅读</div>
        ) : !fileUrl ? (
          <div className="intensive-placeholder">加载中…</div>
        ) : (
          <>
          <div className="paper-toolbar">
            <button className={`mark-read-btn ${readMap[`paper:${selectedId}`] ? 'done' : ''}`} onClick={markRead}>
              {readMap[`paper:${selectedId}`] ? '✓ 已读完' : '标记读完'}
            </button>
          </div>
          <div className="paper-body">
            <div className={`paper-toc ${tocCollapsed ? 'collapsed' : ''}`}>
              <div className="paper-toc-head">
                {tocCollapsed ? (
                  <button className="side-toggle" onClick={() => setTocCollapsed(false)} title="展开目录">»</button>
                ) : (
                  <>
                    <span>目录{sections.length > 0 ? ` · ${sections.length} 节` : ''}</span>
                    <button className="side-toggle" onClick={() => setTocCollapsed(true)} title="收起目录">«</button>
                  </>
                )}
              </div>
              {!tocCollapsed && (sections.length === 0 ? (
                <div className="paper-toc-empty">这篇原文暂未识别出目录</div>
              ) : (
                sections.map((s, i) => (
                  <button key={i} className="paper-toc-item" onClick={() => jumpTo(s.page_range)} title={s.heading}>
                    <span className="paper-toc-heading">{s.heading}</span>
                    {s.page_range && <span className="paper-toc-page">{s.page_range}</span>}
                  </button>
                ))
              ))}
            </div>
            <div className="paper-pdf">
              <Suspense fallback={<div className="intensive-placeholder">PDF 加载中…</div>}>
                <GuidePdfPanel fileUrl={fileUrl} page={currentPage} onClose={null} />
              </Suspense>
            </div>
          </div>
          </>
        )}
      </main>
    </div>
  );
}

export default ReaderPage;
