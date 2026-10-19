import React, { useState, useEffect, useRef, useCallback } from 'react';
// 用 legacy build：pdf.js v6 主构建依赖 Map.prototype.getOrInsertComputed（Firefox 117+ 才支持，Chrome/Safari 会报错），legacy 构建自带 core-js polyfill
import * as pdfjsLib from 'pdfjs-dist/legacy/build/pdf.mjs';
import workerUrl from 'pdfjs-dist/legacy/build/pdf.worker.min.mjs?url';

pdfjsLib.GlobalWorkerOptions.workerSrc = workerUrl;

// 缓存已加载的 PDF 文档，避免重复加载
let _pdfCache = null;
let _pdfCacheUrl = null;

function GuidePdfPanel({ fileUrl, page, onClose }) {
  const scrollRef = useRef(null);
  const containerRef = useRef(null);
  const pageElsRef = useRef({});   // pageNum -> 页容器元素
  const renderedRef = useRef({});   // pageNum -> 是否已渲染
  const scaleRef = useRef(1);
  const lastScrollUpdateRef = useRef(0);

  const [pdf, setPdf] = useState(null);
  const [numPages, setNumPages] = useState(0);
  const [error, setError] = useState('');
  const [mode, setMode] = useState('continuous'); // continuous 连页 | single 单页
  const [scale, setScale] = useState(null); // null=适应宽度
  const [pageHeight, setPageHeight] = useState(0);
  const [currentPage, setCurrentPage] = useState(page || 1);
  const [containerWidth, setContainerWidth] = useState(0);

  // 加载 PDF 文档
  useEffect(() => {
    if (!fileUrl) return;
    let cancelled = false;
    renderedRef.current = {};
    pageElsRef.current = {};
    setNumPages(0);
    setPageHeight(0);
    setCurrentPage(page || 1);
    setError('');
    (async () => {
      try {
        let doc;
        if (_pdfCache && _pdfCacheUrl === fileUrl) doc = _pdfCache;
        else {
          doc = await pdfjsLib.getDocument({ url: fileUrl, disableAutoFetch: true, disableStream: true, rangeChunkSize: 65536 }).promise;
          _pdfCache = doc;
          _pdfCacheUrl = fileUrl;
        }
        if (!cancelled) { setPdf(doc); setNumPages(doc.numPages); }
      } catch (e) {
        if (!cancelled) setError('PDF 加载失败：' + (e?.message || ''));
      }
    })();
    return () => { cancelled = true; };
  }, [fileUrl]);

  // 外部 page 变化（目录点击跳转）：单页翻页，连页滚动到对应页
  useEffect(() => {
    if (!page) return;
    if (mode === 'single') {
      setCurrentPage(page);
    } else {
      const scroll = scrollRef.current;
      if (scroll && pageHeight) {
        scroll.scrollTo({ top: (page - 1) * pageHeight, behavior: 'smooth' });
        setCurrentPage(page);
      }
    }
  }, [page, mode, pageHeight]);

  // 容器宽度（用于适应宽度 + 页高估算）
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const update = () => setContainerWidth(el.clientWidth);
    update();
    let t;
    const onResize = () => { clearTimeout(t); t = setTimeout(update, 200); };
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  // 计算缩放比例 + 统一页高（用第一页宽高比）
  useEffect(() => {
    if (!pdf || !numPages || containerWidth <= 0) return;
    let cancelled = false;
    (async () => {
      try {
        const p1 = await pdf.getPage(1);
        const bv = p1.getViewport({ scale: 1 });
        const s = scale || Math.max(0.5, containerWidth / bv.width);
        scaleRef.current = s;
        if (!cancelled) {
          setPageHeight(Math.round(bv.height * s));
          // 缩放变化 → 清空已渲染页，按新比例重绘
          renderedRef.current = {};
          Object.values(pageElsRef.current).forEach(el => { if (el) el.innerHTML = ''; });
        }
      } catch (e) { /* ignore */ }
    })();
    return () => { cancelled = true; };
  }, [pdf, numPages, containerWidth, scale]);

  // 渲染某一页到其容器
  const renderPage = useCallback(async (pageNum, force = false) => {
    if (!pdf || !scaleRef.current) return;
    const el = pageElsRef.current[pageNum];
    if (!el) return;
    if (!force && renderedRef.current[pageNum]) return;
    renderedRef.current[pageNum] = true;
    try {
      const pdfPage = await pdf.getPage(pageNum);
      const s = scaleRef.current;
      const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
      const vp = pdfPage.getViewport({ scale: s });
      const canvas = document.createElement('canvas');
      canvas.width = vp.width * dpr;
      canvas.height = vp.height * dpr;
      canvas.style.width = vp.width + 'px';
      canvas.style.height = vp.height + 'px';
      canvas.style.display = 'block';
      const ctx = canvas.getContext('2d');
      await pdfPage.render({ canvasContext: ctx, viewport: pdfPage.getViewport({ scale: s * dpr }) }).promise;
      const target = pageElsRef.current[pageNum];
      if (target) { target.innerHTML = ''; target.appendChild(canvas); }
    } catch (e) {
      renderedRef.current[pageNum] = false; // 失败可重试
    }
  }, [pdf]);

  // 连页模式：渲染视口附近页（带一页缓冲区）
  const renderVisible = useCallback(() => {
    const scroll = scrollRef.current;
    if (!scroll || !pageHeight || !numPages) return;
    const top = scroll.scrollTop;
    const bottom = top + scroll.clientHeight;
    const first = Math.max(1, Math.floor((top - pageHeight) / pageHeight));
    const last = Math.min(numPages, Math.ceil((bottom + pageHeight) / pageHeight));
    for (let i = first; i <= last; i++) renderPage(i);
  }, [pageHeight, numPages, renderPage]);

  // 连页模式：滚动监听 + 节流更新当前页
  useEffect(() => {
    if (mode !== 'continuous') return;
    const scroll = scrollRef.current;
    if (!scroll) return;
    const onScroll = () => {
      const now = Date.now();
      if (now - lastScrollUpdateRef.current > 300 && pageHeight > 0) {
        lastScrollUpdateRef.current = now;
        setCurrentPage(Math.max(1, Math.min(numPages, Math.round(scroll.scrollTop / pageHeight) + 1)));
      }
      renderVisible();
    };
    scroll.addEventListener('scroll', onScroll, { passive: true });
    const t = setTimeout(onScroll, 60);
    return () => { clearTimeout(t); scroll.removeEventListener('scroll', onScroll); };
  }, [mode, renderVisible, pageHeight, numPages]);

  // 单页模式：渲染当前页（force，因 slot 每次重建）
  useEffect(() => {
    if (mode !== 'single' || !pdf) return;
    renderPage(currentPage, true);
  }, [mode, currentPage, pdf, scale, containerWidth, renderPage]);

  // 跳转：连页=滚动，单页=翻页
  const goPage = (delta) => {
    if (mode === 'single') {
      setCurrentPage(p => Math.max(1, Math.min(numPages, p + delta)));
    } else {
      const scroll = scrollRef.current;
      if (!scroll || !pageHeight) return;
      const cur = Math.round(scroll.scrollTop / pageHeight) + 1;
      const target = Math.max(1, Math.min(numPages, cur + delta));
      scroll.scrollTo({ top: (target - 1) * pageHeight, behavior: 'smooth' });
    }
  };

  // 键盘 ←→ 翻页
  useEffect(() => {
    if (!pdf) return;
    const onKey = (e) => {
      if (e.key === 'ArrowLeft') { e.preventDefault(); goPage(-1); }
      else if (e.key === 'ArrowRight') { e.preventDefault(); goPage(1); }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pdf, mode, numPages, pageHeight]);

  const zoomIn = () => setScale(Math.round(scaleRef.current * 1.25 * 100) / 100);
  const zoomOut = () => setScale(Math.round(scaleRef.current / 1.25 * 100) / 100);
  const zoom100 = () => setScale(1.0);
  const zoomFit = () => setScale(null);

  const toggleFullscreen = () => {
    const el = containerRef.current;
    if (!el) return;
    if (document.fullscreenElement) document.exitFullscreen();
    else if (el.requestFullscreen) el.requestFullscreen();
    else if (el.webkitRequestFullscreen) el.webkitRequestFullscreen();
  };

  // 连页模式的页容器列表
  const pageList = [];
  for (let i = 1; i <= numPages; i++) {
    pageList.push(
      <div
        key={i}
        data-page={i}
        ref={el => { pageElsRef.current[i] = el; }}
        className="pdf-page-slot"
        style={{ minHeight: pageHeight || 800 }}
      />
    );
  }

  return (
    <div className="guide-pdf-panel" ref={containerRef}>
      <div className="guide-pdf-head">
        <span className="guide-pdf-title">PDF 原文</span>
        <span className="guide-pdf-page">{currentPage} / {numPages}</span>
        <button
          className={`guide-pdf-btn ${mode === 'continuous' ? 'on' : ''}`}
          onClick={() => setMode(mode === 'continuous' ? 'single' : 'continuous')}
          title="连页查看（Continuous Scroll）"
        >{mode === 'continuous' ? '连页' : '单页'}</button>
        <button className="guide-pdf-btn" onClick={() => goPage(-1)} title="上一页（←）">‹</button>
        <button className="guide-pdf-btn" onClick={() => goPage(1)} title="下一页（→）">›</button>
        <button className="guide-pdf-btn" onClick={zoomOut} title="缩小">−</button>
        <button className="guide-pdf-btn" onClick={zoom100} title="原始尺寸 100%">100%</button>
        <button className="guide-pdf-btn" onClick={zoomIn} title="放大">＋</button>
        <button className="guide-pdf-btn" onClick={zoomFit} title="适应宽度">适应</button>
        <button className="guide-pdf-btn" onClick={toggleFullscreen} title="全屏">⛶</button>
        {onClose && <button className="guide-pdf-close" onClick={onClose} title="关闭">✕</button>}
      </div>
      {error ? (
        <div className="guide-pdf-error">{error}</div>
      ) : (
        <div className="guide-pdf-body" ref={scrollRef}>
          {mode === 'continuous' ? (
            <div className="pdf-pages">{pageList}</div>
          ) : (
            <div className="pdf-pages pdf-pages-single">
              <div
                key={currentPage}
                data-page={currentPage}
                ref={el => { pageElsRef.current[currentPage] = el; }}
                className="pdf-page-slot"
                style={{ minHeight: pageHeight || 800 }}
              />
            </div>
          )}
        </div>
      )}
      <div className="guide-pdf-footer">
        <button className="guide-pdf-btn" onClick={() => goPage(-1)} disabled={currentPage <= 1}>‹ 上一页</button>
        <span className="guide-pdf-footer-page">{currentPage} / {numPages}</span>
        <button className="guide-pdf-btn" onClick={() => goPage(1)} disabled={currentPage >= numPages}>下一页 ›</button>
      </div>
    </div>
  );
}

export default GuidePdfPanel;
