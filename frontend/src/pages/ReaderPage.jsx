import React, { useState, useEffect, lazy, Suspense } from 'react';
import { api } from '../api/client';

const GuidePdfPanel = lazy(() => import('../components/GuidePdfPanel'));

// 论文列表模块级缓存（切换 tab 秒出）
let _papersCache = null;

function ReaderPage({ active }) {
  const [papers, setPapers] = useState([]);
  const [papersLoading, setPapersLoading] = useState(true);
  const [selectedId, setSelectedId] = useState(null);
  const [paperDetail, setPaperDetail] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);

  // 加载论文列表
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

  // 有解析中的论文时，轮询刷新状态
  useEffect(() => {
    if (!active) return;
    const hasProcessing = papers.some(p => p.status === 'pending' || p.status === 'processing' || p.status === 'parsed');
    if (!hasProcessing) return;
    const timer = setInterval(() => {
      api.getPapers().then(r => { _papersCache = r.data; setPapers(r.data); }).catch(() => {});
    }, 4000);
    return () => clearInterval(timer);
  }, [active, papers]);

  // 选中论文 → 加载详情（含目录 parsed_structure.sections）
  useEffect(() => {
    if (!selectedId) return;
    setPaperDetail(null);
    setCurrentPage(1);
    api.getPaper(selectedId).then(res => setPaperDetail(res.data)).catch(() => {});
  }, [selectedId]);

  // 上传论文 → 自动解析 → 刷新列表
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

  if (!active) return null;

  const fileUrl = paperDetail?.file_url ? paperDetail.file_url.replace(/^\.\//, '/') : '';
  const sections = paperDetail?.parsed_structure?.sections || [];

  const jumpTo = (pageRange) => {
    const m = String(pageRange || '').match(/\d+/);
    if (m) setCurrentPage(parseInt(m[0], 10));
  };

  return (
    <div className="guide-page">
      <div className="paper-reader">
        {/* 左列：论文列表 + 目录 */}
        <aside className="paper-left">
          <div className="guide-waitlist-head">
            <span>论文列表</span>
            <span className="count">{papers.length}</span>
          </div>
          <div className="guide-upload">
            <label className="guide-upload-label">
              {uploading ? '上传中…' : '📄 上传论文 PDF'}
              <input type="file" accept=".pdf,.epub" onChange={handleUpload} disabled={uploading} style={{ display: 'none' }} />
            </label>
          </div>

          {papersLoading ? (
            <div className="guide-waitlist-empty">加载中…</div>
          ) : papers.length === 0 ? (
            <div className="guide-waitlist-empty">还没有论文，点上面上传 PDF</div>
          ) : (
            papers.map(p => (
              <button
                key={p.id}
                className={`guide-waitlist-item ${p.id === selectedId ? 'active' : ''}`}
                onClick={() => p.status === 'ready' && setSelectedId(p.id)}
                disabled={p.status !== 'ready'}
                title={p.filename}
              >
                <span className="w-name">{p.filename}</span>
                {p.status !== 'ready' && (
                  <span className="w-status">
                    {p.status === 'processing' ? '解析中…' : p.status === 'parsed' ? '准备中…' : p.status === 'error' ? '失败' : '待解析'}
                  </span>
                )}
              </button>
            ))
          )}

          {selectedId && paperDetail && (
            <div className="paper-toc">
              <div className="paper-toc-head">目录{sections.length > 0 ? ` · ${sections.length} 节` : ''}</div>
              {sections.length === 0 ? (
                <div className="paper-toc-empty">这篇论文暂未识别出目录</div>
              ) : (
                sections.map((s, i) => (
                  <button key={i} className="paper-toc-item" onClick={() => jumpTo(s.page_range)} title={s.heading}>
                    <span className="paper-toc-heading">{s.heading}</span>
                    {s.page_range && <span className="paper-toc-page">{s.page_range}</span>}
                  </button>
                ))
              )}
            </div>
          )}
        </aside>

        {/* 右列：PDF 原文（常驻） */}
        <main className="paper-pdf">
          {!selectedId ? (
            <div className="guide-status">← 从左侧选一篇论文查看原文</div>
          ) : !fileUrl ? (
            <div className="guide-status">加载中…</div>
          ) : (
            <Suspense fallback={<div className="guide-status">PDF 加载中…</div>}>
              <GuidePdfPanel fileUrl={fileUrl} page={currentPage} highlight="" onClose={null} />
            </Suspense>
          )}
        </main>
      </div>
    </div>
  );
}

export default ReaderPage;
