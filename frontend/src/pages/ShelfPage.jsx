import React, { useState, useEffect } from 'react';
import { api } from '../api/client';

function ShelfPage({ active, onOpenPaper }) {
  const [papers, setPapers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [reading, setReading] = useState({}); // paperId -> bool

  const loadData = async () => {
    setLoading(true);
    try {
      const res = await api.getPapers();
      setPapers(res.data);
    } catch (err) {
      console.error('Failed to load papers:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (active) loadData();
  }, [active]);

  // 有解析中的论文时，轮询刷新
  useEffect(() => {
    if (!active) return;
    const hasProcessing = papers.some(p => p.status === 'processing' || p.status === 'parsed');
    if (!hasProcessing) return;
    const timer = setInterval(loadData, 4000);
    return () => clearInterval(timer);
  }, [papers, active]);

  const handleUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      await api.uploadPaper(file);
      await loadData();
    } catch (err) {
      alert('上传失败：' + (err.response?.data?.detail || err.message));
    } finally {
      setUploading(false);
      e.target.value = '';
    }
  };

  const handleAiRead = async (paperId) => {
    setReading(prev => ({ ...prev, [paperId]: true }));
    try {
      await api.parsePaper(paperId);
      await loadData();
    } catch (err) {
      alert('解析触发失败：' + (err.response?.data?.detail || err.message));
    } finally {
      setReading(prev => ({ ...prev, [paperId]: false }));
    }
  };

  const statusLabel = (s) => {
    if (s === 'ready') return '已就绪';
    if (s === 'parsed' || s === 'processing') return '解析中';
    if (s === 'pending') return '待 AI 阅读';
    if (s === 'error') return '解析失败';
    return s || '未知';
  };

  if (!active) return null;

  return (
    <div id="page-shelf" className="page active">
      <div className="shelf-header">
        <h2>我的书架</h2>
        <label className="btn-primary" style={{ cursor: 'pointer' }}>
          {uploading ? '上传中…' : '📄 上传 PDF'}
          <input type="file" accept=".pdf,.epub" onChange={handleUpload} style={{ display: 'none' }} />
        </label>
      </div>

      {loading ? (
        <div className="loading">加载中…</div>
      ) : papers.length === 0 ? (
        <div className="empty-state" style={{ padding: '40px', textAlign: 'center', color: 'var(--text-4)' }}>
          还没有论文 —— 点右上角「📄 上传 PDF」或到「市场」下载
        </div>
      ) : (
        <div className="shelf-paper-list">
          {papers.map(p => (
            <div
              key={p.id}
              className="shelf-paper-item"
              onClick={() => p.status === 'ready' && onOpenPaper?.(p.id)}
              style={{ cursor: p.status === 'ready' ? 'pointer' : 'default' }}
            >
              <div className="sp-info">
                <div className="sp-name">{p.filename}</div>
                <div className="sp-meta">
                  <span className={`sp-status st-${p.status}`}>{statusLabel(p.status)}</span>
                  <span> · {new Date(p.created_at).toLocaleDateString()}</span>
                </div>
              </div>
              {p.status === 'ready' ? (
                <button className="btn-add-light" onClick={(e) => { e.stopPropagation(); onOpenPaper?.(p.id); }}>
                  打开导读 →
                </button>
              ) : (p.status === 'pending' || p.status === 'error') ? (
                <button
                  className="btn-add"
                  disabled={reading[p.id]}
                  onClick={(e) => { e.stopPropagation(); handleAiRead(p.id); }}
                >
                  {reading[p.id] ? '触发中…' : '🤖 AI 阅读'}
                </button>
              ) : (
                <button className="btn-add-light" disabled>解析中…</button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default ShelfPage;
