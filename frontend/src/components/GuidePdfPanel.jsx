import React, { useState, useEffect, useRef, useCallback } from 'react';
import * as pdfjsLib from 'pdfjs-dist';
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url';

pdfjsLib.GlobalWorkerOptions.workerSrc = workerUrl;

// 缓存已加载的 PDF 文档，避免重复加载
let _pdfCache = null;
let _pdfCacheUrl = null;

function GuidePdfPanel({ fileUrl, page, highlight, onClose }) {
  const canvasRef = useRef(null);
  const [pdf, setPdf] = useState(null);
  const [hlRect, setHlRect] = useState(null);
  const [scale, setScale] = useState(1.4);
  const [pageInfo, setPageInfo] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [currentPage, setCurrentPage] = useState(page || 1);
  const containerRef = useRef(null);
  const [zoom, setZoom] = useState(null); // null=适应宽度，数字=缩放比例
  const scaleRef = useRef(1);

  // 锚点 page 变化时同步当前页
  useEffect(() => {
    if (page) setCurrentPage(page);
  }, [page]);

  const goPage = (delta) => {
    setCurrentPage(p => {
      const total = pdf?.numPages || p;
      return Math.max(1, Math.min(total, p + delta));
    });
  };

  const toggleFullscreen = () => {
    const el = containerRef.current;
    if (!el) return;
    if (document.fullscreenElement) document.exitFullscreen();
    else if (el.requestFullscreen) el.requestFullscreen();
    else if (el.webkitRequestFullscreen) el.webkitRequestFullscreen();
  };

  const zoomIn = () => setZoom(Math.round(scaleRef.current * 1.25 * 100) / 100);
  const zoomOut = () => setZoom(Math.round(scaleRef.current / 1.25 * 100) / 100);
  const zoom100 = () => setZoom(1.0);
  const zoomFit = () => setZoom(null);

  // 加载 PDF 文档（缓存）
  useEffect(() => {
    if (!fileUrl) return;
    let cancelled = false;
    const load = async () => {
      try {
        let doc = null;
        if (_pdfCache && _pdfCacheUrl === fileUrl) {
          doc = _pdfCache;
        } else {
          doc = await pdfjsLib.getDocument({ url: fileUrl }).promise;
          _pdfCache = doc;
          _pdfCacheUrl = fileUrl;
        }
        if (!cancelled) setPdf(doc);
      } catch (e) {
        if (!cancelled) setError('PDF 加载失败：' + (e?.message || ''));
      }
    };
    load();
    return () => { cancelled = true; };
  }, [fileUrl]);

  // 渲染指定页 + 高亮
  const render = useCallback(async () => {
    if (!pdf || !currentPage) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    try {
      const pdfPage = await pdf.getPage(currentPage);
      const baseViewport = pdfPage.getViewport({ scale: 1 });
      const containerWidth = canvas.parentElement?.clientWidth || 700;
      // 缩放：zoom 优先，否则适应宽度
      let s;
      if (zoom) {
        s = zoom;
      } else {
        s = Math.max(0.5, containerWidth / baseViewport.width);
      }
      scaleRef.current = s;
      setScale(s);

      // devicePixelRatio 提升清晰度（修复 retina 模糊）
      const dpr = window.devicePixelRatio || 1;
      const viewport = pdfPage.getViewport({ scale: s });
      canvas.width = viewport.width * dpr;
      canvas.height = viewport.height * dpr;
      canvas.style.width = viewport.width + 'px';
      canvas.style.height = viewport.height + 'px';
      const ctx = canvas.getContext('2d');
      await pdfPage.render({ canvasContext: ctx, viewport: pdfPage.getViewport({ scale: s * dpr }) }).promise;

      setPageInfo({ num: currentPage, total: pdf.numPages });

      // 高亮文本（viewport/CSS 坐标）
      if (highlight) {
        const textContent = await pdfPage.getTextContent();
        const rect = findHighlightRect(textContent.items, highlight, s);
        setHlRect(rect);
      } else {
        setHlRect(null);
      }
      setLoading(false);
    } catch (e) {
      setError('渲染失败：' + (e?.message || ''));
    }
  }, [pdf, currentPage, highlight, zoom]);

  useEffect(() => { render(); }, [render]);

  return (
    <div className="guide-pdf-panel" ref={containerRef}>
      <div className="guide-pdf-head">
        <span className="guide-pdf-title">PDF 原文</span>
        {pageInfo && <span className="guide-pdf-page">第 {pageInfo.num} / {pageInfo.total} 页</span>}
        <button className="guide-pdf-btn" onClick={() => goPage(-1)} title="上一页">‹</button>
        <button className="guide-pdf-btn" onClick={() => goPage(1)} title="下一页">›</button>
        <button className="guide-pdf-btn" onClick={zoomOut} title="缩小">−</button>
        <button className="guide-pdf-btn" onClick={zoom100} title="原始尺寸 100%">100%</button>
        <button className="guide-pdf-btn" onClick={zoomIn} title="放大">＋</button>
        <button className="guide-pdf-btn" onClick={toggleFullscreen} title="全屏">⛶</button>
        {onClose && <button className="guide-pdf-close" onClick={onClose} title="关闭">✕</button>}
      </div>
      {highlight && (
        <div className="guide-pdf-anchor">
          <span className="guide-pdf-anchor-label">锚点</span>
          <span className="guide-pdf-anchor-text">「{highlight.slice(0, 80)}{highlight.length > 80 ? '…' : ''}」</span>
        </div>
      )}
      <div className="guide-pdf-body">
        {error ? (
          <div className="guide-pdf-error">{error}</div>
        ) : loading ? (
          <div className="guide-pdf-loading">
            <span className="guide-pdf-spinner"></span>
            <span>原文加载中…</span>
          </div>
        ) : (
          <div className="guide-pdf-canvas-wrap">
            <canvas ref={canvasRef} />
            {hlRect && (
              <div
                className="guide-pdf-hl"
                style={{
                  left: hlRect.x,
                  top: hlRect.y,
                  width: hlRect.w,
                  height: hlRect.h,
                }}
              />
            )}
          </div>
        )}
      </div>
      {pageInfo && (
        <div className="guide-pdf-footer">
          <button className="guide-pdf-btn" onClick={() => goPage(-1)} disabled={currentPage <= 1}>‹ 上一页</button>
          <button className="guide-pdf-btn" onClick={zoomOut} title="缩小">−</button>
          <button className="guide-pdf-btn" onClick={zoom100} title="原始尺寸">100%</button>
          <button className="guide-pdf-btn" onClick={zoomIn} title="放大">＋</button>
          <span className="guide-pdf-footer-page">{currentPage} / {pageInfo.total}</span>
          <button className="guide-pdf-btn" onClick={() => goPage(1)} disabled={currentPage >= pageInfo.total}>下一页 ›</button>
        </div>
      )}
    </div>
  );
}

// 在 textContent.items 里查找 highlight 子串，返回覆盖文本的包围盒（viewport 坐标）
function findHighlightRect(items, highlight, scale) {
  if (!items || !items.length || !highlight) return null;
  const needle = highlight.toLowerCase().replace(/\s+/g, '');

  // 拼接全部文本，记录每个 item 的字符范围
  let full = '';
  const ranges = [];
  for (const it of items) {
    if (!it.str) continue;
    const start = full.length;
    full += it.str;
    ranges.push({ item: it, start, end: full.length });
  }
  const compactFull = full.toLowerCase().replace(/\s+/g, '');
  const idx = compactFull.indexOf(needle);
  if (idx < 0) return null;

  // 把 compact 索引映射回原始 full 索引（近似：数到第 idx 个非空白字符）
  let rawStart = 0, seen = 0;
  for (let i = 0; i < full.length; i++) {
    if (seen >= idx) break;
    if (!/\s/.test(full[i])) seen++;
    rawStart = i + 1;
  }
  const rawEnd = rawStart + highlight.length;

  const matched = ranges.filter(r => r.start < rawEnd && r.end > rawStart);
  if (!matched.length) return null;

  const x0 = Math.min(...matched.map(r => r.item.transform[4]));
  const y0 = Math.min(...matched.map(r => r.item.transform[5] - r.item.height));
  const x1 = Math.max(...matched.map(r => r.item.transform[4] + r.item.width));
  const y1 = Math.max(...matched.map(r => r.item.transform[5]));

  return {
    x: x0 * scale,
    y: y0 * scale,
    w: (x1 - x0) * scale,
    h: (y1 - y0) * scale,
  };
}

export default GuidePdfPanel;
