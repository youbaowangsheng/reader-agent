import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';

function PaperList() {
  const [papers, setPapers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);

  const fetchPapers = async () => {
    try {
      const res = await api.getPapers();
      setPapers(res.data);
    } catch (err) {
      console.error('Failed to fetch papers:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPapers();
    // Auto-refresh every 5 seconds to see status changes
    const interval = setInterval(fetchPapers, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setUploading(true);
    try {
      const res = await api.uploadPaper(file);
      alert(`上传成功: ${res.data.filename}`);
      fetchPapers();
    } catch (err) {
      alert('上传失败');
    } finally {
      setUploading(false);
    }
  };

  const handleParse = async (paperId) => {
    try {
      await api.parsePaper(paperId);
      alert('解析任务已启动，解析完成后状态会变成"ready"');
      fetchPapers();
    } catch (err) {
      alert('解析启动失败');
    }
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h2>📚 我的论文</h2>
        <button onClick={fetchPapers} style={{ padding: '8px 16px' }}>🔄 刷新</button>
      </div>

      <div className="upload-area">
        <label className="upload-label">
          {uploading ? '上传中...' : '📄 点击上传 PDF/EPUB'}
          <input type="file" accept=".pdf,.epub" onChange={handleUpload} disabled={uploading} />
        </label>
      </div>

      {loading ? (
        <p>加载中...</p>
      ) : papers.length === 0 ? (
        <p style={{ textAlign: 'center', color: '#888' }}>暂无论文，上传 PDF 或 EPUB 开始阅读</p>
      ) : (
        <div className="paper-list">
          {papers.map(paper => (
            <div key={paper.id} className="paper-card" style={{ padding: '20px' }}>
              <h3 style={{ marginBottom: 8 }}>{paper.filename}</h3>
              <div className="meta" style={{ marginBottom: 12 }}>上传于 {new Date(paper.created_at).toLocaleDateString()}</div>
              <span style={{ display: 'inline-block', padding: '4px 12px', borderRadius: '4px', fontSize: '12px', fontWeight: 'bold', marginBottom: 8,
                background: paper.status === 'ready' ? '#d4edda' : paper.status === 'processing' ? '#cce5ff' : paper.status === 'error' ? '#f8d7da' : '#fff3cd',
                color: paper.status === 'ready' ? '#155724' : paper.status === 'processing' ? '#004085' : paper.status === 'error' ? '#721c24' : '#856404'
              }}>
                {paper.status === 'pending' ? '⏳ 待解析' :
                 paper.status === 'processing' ? '🔄 解析中...' :
                 paper.status === 'ready' ? '✅ 可阅读' :
                 paper.status === 'error' ? '❌ 失败' : paper.status}
              </span>
              {paper.status === 'pending' && (
                <button
                  onClick={() => handleParse(paper.id)}
                  style={{
                    marginTop: 8,
                    marginRight: 8,
                    padding: '10px 20px',
                    background: '#007bff',
                    color: 'white',
                    border: 'none',
                    borderRadius: '6px',
                    cursor: 'pointer',
                    fontSize: '14px',
                    fontWeight: 'bold',
                  }}
                >
                  ▶ 开始解析
                </button>
              )}
              {paper.status === 'ready' && (
                <Link to={`/paper/${paper.id}`}>
                  <button style={{
                    marginTop: 8,
                    padding: '10px 20px',
                    background: '#28a745',
                    color: 'white',
                    border: 'none',
                    borderRadius: '6px',
                    cursor: 'pointer',
                    fontSize: '14px',
                    fontWeight: 'bold',
                  }}>
                    📖 阅读
                  </button>
                </Link>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default PaperList;