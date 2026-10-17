import React, { useState, useEffect, useRef } from 'react';
import { api } from '../api/client';

function ShelfPage({ active }) {
  const [magazines, setMagazines] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [expanded, setExpanded] = useState(null);
  const [detail, setDetail] = useState(null);
  const [importing, setImporting] = useState({});
  const fileInputRef = useRef(null);

  const loadMagazines = () => {
    api.getMagazines().then(r => setMagazines(r.data)).catch(() => {});
  };

  useEffect(() => {
    if (active) loadMagazines();
  }, [active]);

  const handleUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const res = await api.uploadMagazine(file);
      setDetail(res.data);
      setExpanded(res.data.id);
      loadMagazines();
    } catch (err) {
      alert('上传失败：' + (err.response?.data?.detail || err.message));
    } finally {
      setUploading(false);
      e.target.value = '';
    }
  };

  const toggleExpand = (id) => {
    if (expanded === id) {
      setExpanded(null); setDetail(null);
    } else {
      setExpanded(id);
      api.getMagazine(id).then(r => setDetail(r.data)).catch(() => {});
    }
  };

  const handleImport = async (id) => {
    setImporting(i => ({ ...i, [id]: true }));
    try {
      await api.importMagazine(id);
      pollStatus(id);
    } catch (err) {
      alert('导入失败');
      setImporting(i => ({ ...i, [id]: false }));
    }
  };

  const pollStatus = (id) => {
    const timer = setInterval(() => {
      api.getMagazine(id).then(r => {
        const m = r.data;
        setDetail(m);
        if (m.status === 'done' || m.status === 'empty') {
          clearInterval(timer);
          setImporting(i => ({ ...i, [id]: false }));
          loadMagazines();
        }
      }).catch(() => {
        clearInterval(timer);
        setImporting(i => ({ ...i, [id]: false }));
      });
    }, 2000);
  };

  const statusLabel = (s) => {
    if (s === 'split') return '已拆分';
    if (s === 'importing') return '导入中';
    if (s === 'done') return '已入库';
    if (s === 'empty') return '未拆出文章';
    return s || '未知';
  };

  if (!active) return null;

  return (
    <div id="page-shelf" className="page active">
      <div className="shelf-header">
        <h2>书架</h2>
        <button className="btn-primary" onClick={() => fileInputRef.current?.click()} disabled={uploading}>
          {uploading ? '上传中…' : '📄 上传杂志 PDF'}
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept="application/pdf,.pdf"
          onChange={handleUpload}
          style={{ position: 'absolute', width: '1px', height: '1px', opacity: 0, overflow: 'hidden' }}
        />
      </div>

      <div className="shelf-hint">上传一期杂志/期刊 PDF，自动拆成多篇文章，评级后入库到「精读」或「泛读」语料</div>

      {magazines.length === 0 ? (
        <div className="empty-state" style={{ padding: '40px', textAlign: 'center', color: 'var(--text-4)' }}>
          还没有杂志 —— 点右上角「📄 上传杂志 PDF」
        </div>
      ) : (
        <div className="shelf-paper-list">
          {magazines.map(m => (
            <div key={m.id} className="magazine-block">
              <div className="shelf-paper-item" onClick={() => toggleExpand(m.id)}>
                <div className="sp-info">
                  <div className="sp-name">{m.filename}</div>
                  <div className="sp-meta">
                    <span className={`sp-status ${m.status === 'done' ? 'st-ready' : m.status === 'importing' ? 'st-processing' : ''}`}>
                      {statusLabel(m.status)}
                    </span>
                    <span> · {m.article_count} 篇文章</span>
                    {m.imported && (m.imported.intensive > 0 || m.imported.extensive > 0) && (
                      <span> · 入库 精读{m.imported.intensive} / 泛读{m.imported.extensive}</span>
                    )}
                  </div>
                </div>
                <button
                  className="btn-add"
                  disabled={importing[m.id] || m.status === 'empty'}
                  onClick={(e) => { e.stopPropagation(); handleImport(m.id); }}
                >
                  {importing[m.id] ? '导入中…' : m.status === 'done' ? '重新入库' : '🤖 评级入库'}
                </button>
              </div>

              {expanded === m.id && detail && (
                <div className="magazine-articles">
                  {(detail.articles || []).map((a, i) => (
                    <div className="magazine-article-item" key={i}>
                      <span className="ma-title">{a.title}</span>
                      <span className="ma-meta">{a.word_count}词{a.author ? ` · ${a.author}` : ''}</span>
                    </div>
                  ))}
                  {(!detail.articles || detail.articles.length === 0) && (
                    <div className="magazine-articles-empty">未拆出文章（可能不是标准杂志排版）</div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default ShelfPage;
