import React, { useState, useEffect } from 'react';
import { api } from '../api/client';

function ShelfPage({ active }) {
  const [papers, setPapers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedPaper, setSelectedPaper] = useState(null);

  useEffect(() => {
    if (active) loadData();
  }, [active]);

  const loadData = async () => {
    setLoading(true);
    try {
      const res = await api.getPapers();
      setPapers(res.data);
      if (res.data.length > 0 && !selectedPaper) setSelectedPaper(res.data[0]);
    } catch (err) {
      console.error('Failed to load papers:', err);
    } finally {
      setLoading(false);
    }
  };

  const demoProjects = [
    { id: 'proj-1', name: '2025 综述写作', meta: `${papers.filter(p => p.status === 'ready').length} 篇文献 · 更新于 2 小时前`, papers: papers.filter(p => p.status === 'ready').slice(0, 2) },
    { id: 'proj-2', name: '大模型推理优化', meta: `${papers.length} 篇文献 · 更新于 昨天`, papers: papers.filter(p => p.status === 'ready').slice(2, 4) },
    { id: 'proj-3', name: '组会下周讨论', meta: '2 篇文献 · 更新于 3 天前', papers: [] }
  ];

  const unreadPapers = papers.filter(p => !p.filename?.includes('综述') && !p.filename?.includes('推理'));

  if (!active) return null;

  return (
    <div id="page-shelf" className="page active">
      <div className="shelf-header">
        <h2>我的书架</h2>
        <button className="btn-primary">新建项目</button>
      </div>
      {loading ? (
        <div className="loading">加载中…</div>
      ) : (
        <>
          <div className="project-grid">
            {demoProjects.map(proj => (
              <div key={proj.id} className="project-card">
                <div className="title">{proj.name}</div>
                <div className="meta">{proj.meta}</div>
                {proj.papers.map((p, i) => (
                  <div
                    key={p.id || i}
                    className="paper-item"
                    onClick={() => {
                      setSelectedPaper(p);
                      window.dispatchEvent(new CustomEvent('reader:openPaper', { detail: p }));
                    }}
                  >
                    <span>{p.filename || '未命名论文'}</span>
                    <span><span className="density-bar"><span className="fill" style={{ width: '60%' }}></span></span></span>
                  </div>
                ))}
              </div>
            ))}
          </div>
          <div className="inbox-area">未整理草稿箱（{unreadPapers.length} 篇待分类）—— 点击论文卡片阅读后自动归类</div>
        </>
      )}
    </div>
  );
}

export default ShelfPage;
